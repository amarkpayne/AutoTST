#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import os.path
import logging
#FORMAT = "%(filename)s:%(lineno)d %(funcName)s %(levelname)s %(message)s"
#logging.basicConfig(format=FORMAT, level=logging.iNFO)

import pylab
import scipy.stats
import matplotlib
matplotlib.rc('mathtext', fontset='stixsans', default='regular')
import re
import rmgpy
from rmgpy.quantity import constants
from rmgpy.kinetics import Arrhenius, ArrheniusEP, KineticsData
from autotst.database import *
from rmgpy.species import Species
from rmgpy.data.rmg import RMGDatabase

from collections import defaultdict, OrderedDict
import pandas as pd
import itertools


def get_unknown_species(reactions, known_species):
    """
    Expects list of auto-TST reactions and known species dictionary

    Returns unique list of species (as SMILES) from the reactions not in the dictionary
    """
    found_species = {}
    need_to_add = []

    for i, reaction in enumerate(reactions):
        rmg_reaction = reaction.rmg_reaction
        r1, r2 = rmg_reaction.reactants
        p1, p2 = rmg_reaction.products

        relavent_species = [r1, r2, p1, p2]
        relavent_labels = {}

        for rel_species in relavent_species:
            for label in known_species:
                known_spec = known_species[label]
                if known_spec.isIsomorphic(rel_species):
                    found_species[rel_species] = label
                    relavent_labels[rel_species] = label

            if rel_species not in found_species.keys():
                need_to_add.append(rel_species.toSMILES())

    need_to_add = list(set(need_to_add))

    return need_to_add


def update_dictionary_entries(old_entries, need_to_add):
    """
    Expects dictionary of species entries and
    unique list of species (as SMILES) that need to be added

    Creates new entries for the species that need to be added
    Returns old and new entries
    """
    list(set(need_to_add))
    for j, species in enumerate(need_to_add):

        molecule = Molecule(SMILES=species)
        adjlist = molecule.toAdjacencyList()

        multiplicity = None
        if re.search('(?<=multiplicity ).*', adjlist):
            multiplicity = int(
                re.search('(?<=multiplicity ).*', adjlist).group(0))
            adjlist = re.sub(r'multiplicity .*',
                             'multiplicity [{}]'.format(multiplicity), adjlist)

        group = rmgpy.molecule.group.Group()
        group.fromAdjacencyList(adjlist)

        atom_counts = {}
        rel_label = ''
        for atom in ['C', 'H', 'O']:
            count = species.count(atom)
            if count > 0:
                rel_label = rel_label + atom + str(count)

        assert rel_label != ''

        """
        3 Scenerios:
        No old -> no need for ID number: max_ID = -1
        Only one old -> needs to have ID of 1: max_ID = 0
        Multiple old -> needs to have a unique ID: max_ID > 0
        """

        new_ID = None
        max_ID = -1
        duplicate = False
        for old_label in old_entries:
            old_entry = old_entries[old_label]

            if group.isIsomorphic(old_entry.item):
                duplicate = True
                print '{} found to be duplicate'.format(old_entry)
                continue

            if rel_label not in old_label:
                continue

            if rel_label == old_label and max_ID == -1:
                # Atleast one with same label
                max_ID = 0

            if old_label.find('-') > 0:
                old_label, ID_str = old_label.split('-')
                ID = int(ID_str)

                if old_label == rel_label and ID > max_ID:
                    # Multiple exisitng labels
                    max_ID = ID

        if max_ID > -1:
            # Existing label
            new_ID = max_ID + 1
            rel_label = rel_label + '-' + str(new_ID)

        if not duplicate:
            entry = Entry()
            entry.label = rel_label
            entry.item = group
            assert rel_label not in old_entries.keys()
            old_entries[rel_label] = entry

    entry_labels = [old_entries[key].label for key in old_entries]
    assert len(entry_labels) == len(list(set(entry_labels))
                                    ), 'Non-unique labels in dictionary'

    return old_entries


def check_dictionary_entries(dict_entries):
    """
    Simple check that there are no entries with duplicate adjacency lists or labels
    """
    entry_adjlists = []
    entry_labels = []
    for entry in dict_entries.values():
        adjlist = entry.item.toAdjacencyList()

        assert adjlist not in entry_adjlists, 'Non-unique adjacencies for dictionary'
        assert entry.label not in entry_labels, 'Non-unique labels for dictionary'

        entry_adjlists.append(entry.item.toAdjacencyList())
        entry_labels.append(entry.label)

    return True


def rote_load_dict(path):
    """
    Expects path to dictionary with multiplictiy formatted as int instead of list

    Returns list of the entries of that dictionary
    """
    with open(path, 'r') as f:
        entries_str = f.read().split('\n\n')

    entries = {}
    for entry_str in entries_str:
        label, adjlist = entry_str.split('\n', 1)

        if re.search('(?<=multiplicity ).*', adjlist):
            multiplicity = int(
                re.search('(?<=multiplicity ).*', adjlist).group(0))
            adjlist = 'multiplicity [{}]\n'.format(
                multiplicity) + adjlist.split('\n', 1)[1]

        group = rmgpy.molecule.group.Group()
        group.fromAdjacencyList(adjlist)

        entry = Entry()
        entry.item = group
        entry.label = label
        entries[label] = entry

    return entries


def rote_save_dictionary(path, entries):
    """
    Expects path to where the new dictionary should be saved and a list of the dictionaries entries

    Saves dictionary with multiplicty formatted as int instead of list
    """
    f = open(path, 'w')

    for entry in entries.values():
        multiplicity = entry.item.multiplicity
        adjlist = entry.item.toAdjacencyList()

        if multiplicity is not None:
            adjlist = re.sub('\[', '', adjlist)
            adjlist = re.sub('\]', '', adjlist)

        f.write(entry.label)
        f.write('\n')
        f.write(adjlist)
        f.write('\n')

    f.close()
    return


def update_known_reactions(path, reactions, known_species, method='', shortDesc=''):
    """
    Expects path of current reactions database, new reactions to add as list of auto-TST reaction objects,
        an updated known_species dict (includes species in new reactions),
        and methods and shortDesc for the new Reactions

    Returns database object of both old and new reactions, just the old reactions, and just the new reactions
    """
    # Loading reactions database
    from autotst.database import TransitionStateDepository, DistanceData
    r_db = TransitionStateDepository()
    local_context = {'DistanceData': DistanceData}
    r_db.load(path, local_context=local_context)

    # Old r_db only has reactions already in reactions.py
    old_r_db = TransitionStateDepository()
    old_r_db.load(path, local_context=local_context)

    # New r_db will contain new reactions from the csv_df
    new_r_db = TransitionStateDepository()

    found_species = {}
    need_to_add = []

    Index = 0
    for entry in r_db.entries.values():
        if Index < entry.index:
            Index = entry.index
    Index = Index + 1

    for i, reaction in enumerate(reactions):
        Distances = reaction.distance_data.distances
        distance_data = DistanceData(distances=Distances, method=method)

        rmg_reaction = reaction.rmg_reaction
        r1, r2 = rmg_reaction.reactants
        p1, p2 = rmg_reaction.products

        relavent_species = [r1, r2, p1, p2]
        relavent_labels = {}

        for rel_species in relavent_species:
            for label in known_species:
                known_spec = known_species[label]
                if known_spec.isIsomorphic(rel_species):
                    found_species[rel_species] = label

            if rel_species not in found_species.keys():
                need_to_add.append(rel_species.toSMILES())
                logging.warning(
                    '{} not found in species dictionary'.format(rel_species))

        lr1 = found_species[r1]
        lr2 = found_species[r2]
        lp1 = found_species[p1]
        lp2 = found_species[p2]

        Label = '{} + {} <=> {} + {}'.format(lr1, lr2, lp1, lp2)
        #print Label

        # adding new entries to r_db, r_db will contain old and new reactions
        r_db.loadEntry(Index + i,
                       reactant1=None,
                       reactant2=None,
                       reactant3=None,
                       product1=None,
                       product2=None,
                       product3=None,
                       distances=distance_data,
                       degeneracy=1,
                       label=Label,
                       duplicate=False,
                       reversible=True,
                       reference=None,
                       referenceType='',
                       shortDesc=shortDesc,
                       longDesc='',
                       rank=None,
                       )

        r_db.entries['{0:d}:{1}'.format(Index + i, Label)].item = rmg_reaction

        # Adding new reactions to the new r_db as well
        new_r_db.loadEntry(Index + i,
                           reactant1=None,
                           reactant2=None,
                           reactant3=None,
                           product1=None,
                           product2=None,
                           product3=None,
                           distances=distance_data,
                           degeneracy=1,
                           label=Label,
                           duplicate=False,
                           reversible=True,
                           reference=None,
                           referenceType='',
                           shortDesc=shortDesc,
                           longDesc='',
                           rank=None,
                           )

        new_r_db.entries['{0:d}:{1}'.format(
            Index + i, Label)].item = rmg_reaction

    need_to_add = list(set(need_to_add))

    assert len(need_to_add) == 0, 'Species missing from dictionary'
    assert len(r_db.entries) > len(old_r_db.entries) and len(
        r_db.entries) > len(new_r_db.entries)
    assert len(r_db.entries) == len(old_r_db.entries) + len(new_r_db.entries)

    return r_db, old_r_db, new_r_db


def update_databases(reactions, method='', shortDesc='', reaction_family=''):
    """
    Expects list of auto-TST reaction objects to add to the current dictionary,
        method, shortDesc, and reaction family of those Reactions

    Saves the new reactions and new species found in those reactions
    """

    import logging
    import os

    assert isinstance(
        reactions, list), 'Must provide list of auto-TST reaction objects even if there is only one reaction'
    assert len(reactions) > 0

    if reaction_family == '':
        reaction_family = 'H_Abstraction'
        logging.warning(
            'Defaulting to reaction family of {}'.format(reaction_family))

    general_path = os.path.join(os.path.expandvars(
        '$RMGpy'), '..', 'AutoTST', 'database', reaction_family, 'TS_training')
    dict_path = os.path.join(general_path, 'dictionary.txt')
    new_dict_path = os.path.join(general_path, 'updated_dictionary.txt')
    old_reactions_path = os.path.join(general_path, 'reactions.py')
    new_reactions_path = os.path.join(general_path, 'updated_reactions.py')

    known_species = rmgpy.data.base.Database().getSpecies(dict_path)
    unknown_species = get_unknown_species(reactions, known_species)

    updated_known_species = []
    if len(unknown_species) > 0:
        old_dict_entries = rote_load_dict(dict_path)

        assert len(known_species) == len(old_dict_entries)

        all_dict_entries = update_dictionary_entries(
            old_dict_entries, unknown_species)
        assert len(known_species) + \
            len(unknown_species) == len(all_dict_entries)

        if check_dictionary_entries(all_dict_entries):
            rote_save_dictionary(new_dict_path, all_dict_entries)

        updated_known_species = rmgpy.data.base.Database().getSpecies(new_dict_path)
        unk_spec = get_unknown_species(reactions, updated_known_species)
        assert len(unk_spec) == 0, '{} unknown species found after updating'.format(
            len(unk_spec))
    else:
        updated_known_species = known_species

    r_db, old_db, new_db = update_known_reactions(old_reactions_path,
                                                  reactions,
                                                  updated_known_species,
                                                  method=method,
                                                  shortDesc=shortDesc
                                                  )

    # TODO add check for duplicates method
    # if check_reactions_database():
    if True:
        logging.warning('No duplicate check for reactions database')
        r_db.save(new_reactions_path)
        if len(reactions) < 5:
            for reaction in reactions:
                logging.info(
                    '{} saved and species dictionary updated'.format(reaction))
        else:
            logging.info('Reactions and their species saved to...\n{}\n...and...\n{}\n...respectively'.format(
                new_reactions_path, new_dict_path))
    return

#################################################################################################################################


def TS_Database_Update(families, path=None, auto_save=False):
    """
    Expects list of reaction families

    Loads RMG Databse,
    Creaes instance of TS_updater for each reaction family in families,

    Return dictionary of family:family's instance of the updater
    """

    assert isinstance(
        families, list), "Families must be a list. If singular family, still keep it in list"
    acceptable_families = os.listdir(os.path.join(
        os.path.expandvars("$RMGpy"), "..", "AutoTST", "database"))
    for family in families:
        assert isinstance(
            family, str), "Family names must be provided as strings"
        if family.upper() not in (family.upper() for family in acceptable_families):
            logging.warning(
                '"{}" is not a known Kinetics Family'.format(family))
            families.remove(family)

    logging.info("Loading RMG Database...")
    rmg_database = RMGDatabase()
    database_path = os.path.join(os.path.expandvars(
        '$RMGpy'), "..",  'RMG-database', 'input')

    try:
        rmg_database.load(database_path,
                          # kineticsFamilies=['H_Abstraction'],
                          kineticsFamilies=families,
                          transportLibraries=[],
                          reactionLibraries=[],
                          seedMechanisms=[],
                          thermoLibraries=[
                              'primaryThermoLibrary', 'thermo_DFT_CCSDTF12_BAC', 'CBS_QB3_1dHR'],
                          solvation=False,
                          )
    except:
        logging.error(
            "Failed to Load RMG Database at {}".format(database_path))

    Databases = {family: TS_Updater(
        family, rmg_database, path=path) for family in families}

    if auto_save == True:
        save_all_individual_databases(Databases)

    return Databases


def save_all_individual_databases(instances):
    """
    Expects dict of family:TS_Updater instance
    """
    for family in instances:
        database = instances[family]
        database.save_database()
    return

######################################################


class TS_Updater:
    """
    Class for use in updating TS training databases (functional group contributions to TS geo.)

    Attributes:
    self.family                 : Relavent Reaction Family
    self.path                   : Path to family
    self.database               : Source for TS geometries
    self.training_set           : Lists of Reaction and corresponding TS Geometries

    self.top_nodes              : The two top nodes of the tree of related structures
    self.all_entries            : All the nodes in the tree

    self.direct_groups          : Group that is directly matched with reactant structure
    self.nodes_to_update        : Unique list of direct groups and their ancestors
    self.group_ancestors        : Dict organized by {direct group: list of direct groups and its ancestors}
    self.reaction_templates     : The two groups associated with a given reaction's reactants, organized by reaction

    self.groupComments          : Templates that are relavent to that entry
    self.groupCounts            : Number of relavant combinations of groups that contribute to that entry
    self.groupUncertainties     : Uncertainty in the optimized TS geometry for that node/entry
    self.groupValues            : Optimized TS geometry for that node/entry

    self.A                      : Binary Matrix of groups involved in specific reaction, is of size (all combinations of those relavent groups for all reactions) by (relavant groups + 1)
    self.b                      : Ax=b, x is unknown, b is distance data and is of size (all combinations of relavent groups for all reactions) by (3 distances)
    """

    def __init__(self, family, rmg_database, path=None):

        if path is not None:
            self.path = path
        else:
            self.path = os.path.join(os.path.expandvars(
                "$RMGpy"), "..", "AutoTST", "database", family)

        self.family = family

        self.set_TS_training_data(rmg_database)

        self.update_indices()
        self.set_group_info()
        self.initialize_entry_attributes()
        self.adjust_distances()
        self.set_entry_data()

    def set_TS_training_data(self, rmg_database):
        """
        Loads Database, sets it as class attribute, sets training_set from database
        """
        from autotst.database import DistanceData, TransitionStateDepository, TSGroups, TransitionStates
        ts_database = TransitionStates()
        #path = os.path.join(os.path.expandvars("$RMGpy"), "..", "AutoTST", "database", self.family)
        path = self.path
        global_context = {'__builtins__': None}
        local_context = {'DistanceData': DistanceData}
        assert self.family in rmg_database.kinetics.families.keys(
        ), "{} not found in kinetics families. Could not Load".format(family)
        family = rmg_database.kinetics.families[self.family]
        ts_database.family = family
        ts_database.load(path, local_context, global_context)
        self.database = ts_database
        # Reaction must be a template reaction... found above

        logging.info("Getting Training Data for {}".format(family))
        training_data = [(entry.item, entry.data.distances)
                         for entry in list(ts_database.depository.entries.itervalues())]
        self.training_set = training_data
        logging.info("Total Distances Count: {}".format(
            len(self.training_set)))
        return

    def update_indices(self):
        """
        Updating entry indices based off of tree indices, tree indices are found by descending the tree
        Without this, indices will be based off of previous database which may not be aligned by the current tree
        """
        all_entries = []
        self.top_nodes = self.database.groups.top
        assert len(self.top_nodes) == 2, 'Only set to work for trees with two top nodes. It has: {}'.format(
            len(self.top_nodes))

        for top_node in self.top_nodes:
            descendants = [top_node] + \
                self.database.groups.descendants(top_node)
            all_entries.extend(descendants)

        for tree_index, entry in enumerate(all_entries):
            #tree_indices[entry] = tree_index
            self.database.groups.entries[entry.label].index = tree_index
            entry.index = tree_index

        self.all_entries = all_entries
        logging.info("Updating Indices based off of Tree...")
        logging.info("Tree size: {}".format(len(all_entries)))
        return

    def set_group_info(self):
        """
        Sets useful group info that is used by further class methods
        """

        # Direct groups are the lowest level node that matches the reactant structure
        direct_groups = []
        # the two groups (template) of the reactants organized by reactions
        all_reactant_groups = {}

        for reaction, distance_data in self.training_set:
            reactant_groups = []  # The groups that represent each reactant - also known as the templat

            for top_node in self.top_nodes:

                for reactant in reaction.reactants:
                    if isinstance(reactant, rmgpy.species.Species):
                        reactant = reactant.molecule[0]

                    atoms = list(reactant.getLabeledAtoms().itervalues())
                    assert atoms is not None

                    #temp_group = self.database.groups.descendTree(reactant, atoms, root=top_node)
                    temp_group = self.database.groups.descendTree(
                        reactant, atoms, root=top_node)
                    if temp_group is not None:  # Temp_group will only be found using one of the two top_nodes
                        reactant_group = temp_group
                        break

                reactant_groups.append(reactant_group)
                direct_groups.append(reactant_group)

            # storing the templates by reaction
            all_reactant_groups[reaction] = reactant_groups

        direct_groups = list(set(direct_groups))
        direct_groups.sort(key=lambda x: x.index)

        all_ancestors = {}  # Key is group, value is its itself and all its ancestors
        for direct_group in direct_groups:
            ancestors = [direct_group] + \
                self.database.groups.ancestors(direct_group)
            for ancestor in ancestors:
                if ancestor in all_ancestors.keys():
                    continue
                else:
                    all_ancestors[ancestor] = [ancestor] + \
                        self.database.groups.ancestors(ancestor)

        # We need a list of unique nodes that are directly involved in a reaction or the ancestor of a group that is
        nodes_to_update = [
            group for group in all_ancestors if group not in self.top_nodes]
        nodes_to_update.sort(key=lambda x: x.index)

        # Group info that is needed to simplify following methods
        self.direct_groups = direct_groups
        self.nodes_to_update = nodes_to_update
        self.group_ancestors = all_ancestors
        self.reaction_templates = all_reactant_groups

        logging.info('Nodes to Update: {}'.format(len(self.nodes_to_update)))
        logging.info("Reaction Templates: {}".format(
            len(self.reaction_templates)))
        return

    def initialize_entry_attributes(self):
        """
        Attributes of each entry, initializing to size of all_entries
        """
        self.groupComments = {}
        self.groupCounts = {}
        self.groupUncertainties = {}
        self.groupValues = {}
        for entry in self.all_entries:
            self.groupComments[entry] = set()
            self.groupCounts[entry] = []
            self.groupUncertainties[entry] = []
            self.groupValues[entry] = []
        return

    def adjust_distances(self):
        """
        Creating A and b of Ax=b, where b is distance data and x are groups involved
        A is optimized group contributions (found next in self.set_entry_data)
        """
        def getAllCombinations(nodeLists):
            """
            From base.py:
            Generate a list of all possible combinations of items in the list of
            lists `nodeLists`. Each combination takes one item from each list
            contained within `nodeLists`. The order of items in the returned lists
            reflects the order of lists in `nodeLists`. For example, if `nodeLists` was
            [[A, B, C], [N], [X, Y]], the returned combinations would be
            [[A, N, X], [A, N, Y], [B, N, X], [B, N, Y], [C, N, X], [C, N, Y]].
            """

            items = [[]]
            for nodeList in nodeLists:
                items = [item + [node] for node in nodeList for item in items]

            return items
        ###################

        distance_keys = sorted(self.training_set[0][1].keys())
        # distance_keys are ['d12', 'd13', 'd23']

        A = []
        b = []
        for reaction, distance_data in self.training_set:
            template = self.reaction_templates[reaction]
            distances_list = [distance_data[key] for key in distance_keys]

            relavent_combinations = []
            for reactant_group in template:
                relavent_combinations.append(
                    self.group_ancestors[reactant_group])
            # will throw if reaction does not have 2 reactants
            assert len(relavent_combinations) == 2

            relavent_combinations = getAllCombinations(relavent_combinations)
            # rel_comb is just all combinations of reactant1 and its ancestors with reactant2 and its ancestors

            for combination in relavent_combinations:
                Arow = [
                    1 if group in combination else 0 for group in self.nodes_to_update]
                Arow.append(1)  # For use in finding the family component
                # Arow is a binary vector of len(groupList)+1 representing contributing groups to this reaction's distance data
                A.append(Arow)
                b.append(distances_list)
                for group in combination:
                    if isinstance(group, str):
                        assert False, "Discrepancy between versions of RMG_Database and this one"

                    self.groupComments[group].add('{0!s}'.format(template))

        self.A = numpy.array(A)
        self.b = numpy.array(b)
        return

    def set_entry_data(self):
        """
        Using A and b to find stats for relavent nodes of tree

        Needs to follow self.adjust_distances() so that self.A and self.b are set

        Pseudo explaination:
        Groups M and N are associated with a reaction that has a known ts geometry
        Groups M, N, and the family component must add together to get as close to that geometry as possible
        M and N are optimized based off of all reactionas they are involved with, and the family component is optimized over all reactions of that family
        """
        import scipy.stats

        distance_keys = sorted(self.training_set[0][1].keys())
        # distance_keys are ['d12', 'd13', 'd23']

        x, residuals, rank, s = numpy.linalg.lstsq(self.A, self.b)
        for i, distance_key in enumerate(distance_keys):
            # Determine error in each group
            variance_sums = numpy.zeros(
                len(self.nodes_to_update)+1, numpy.float64)
            stdev = numpy.zeros(len(self.nodes_to_update)+1, numpy.float64)
            counts = numpy.zeros(len(self.nodes_to_update)+1, numpy.int)

            for reaction, distances in self.training_set:
                template = self.reaction_templates[reaction]

                distances_list = [distances[key] for key in distance_keys]
                d = numpy.float64(distances_list[i])
                # dm found by manually summing residuals
                dm = x[-1, i] + sum([x[self.nodes_to_update.index(group), i]
                                     for group in template])

                variance = (dm - d)**2

                for group in template:
                    for ancestor in self.group_ancestors[group]:
                        if ancestor not in self.top_nodes:
                            ind = self.nodes_to_update.index(ancestor)
                            variance_sums[ind] += variance
                            counts[ind] += 1
                variance_sums[-1] += variance
                counts[-1] += 1

            ci = numpy.zeros(len(counts))

            for j, count in enumerate(counts):
                if count > 2:
                    stdev[j] = numpy.sqrt(variance_sums[j] / (count - 1))
                    ci[j] = scipy.stats.t.ppf(0.975, count - 1) * stdev[j]
                else:
                    stdev[j] = None
                    ci[j] = None

            # Update dictionaries of fitted group values and uncertainties
            for entry in self.all_entries:
                if entry == self.top_nodes[0]:
                    self.groupValues[entry].append(x[-1, i])
                    self.groupUncertainties[entry].append(ci[-1])
                    self.groupCounts[entry].append(counts[-1])
                elif entry.label in [group.label for group in self.nodes_to_update]:
                    index = self.nodes_to_update.index(entry)

                    self.groupValues[entry].append(x[index, i])
                    self.groupUncertainties[entry].append(ci[index])
                    self.groupCounts[entry].append(counts[index])
                else:
                    self.groupValues[entry] = None
                    self.groupUncertainties[entry] = None
                    self.groupCounts[entry] = None

            for entry in self.all_entries:
                if self.groupValues[entry] is not None:
                    if not any(numpy.isnan(numpy.array(self.groupUncertainties[entry]))):
                        # should be entry.data.* (e.g. entry.data.uncertainties)
                        uncertainties = numpy.array(
                            self.groupUncertainties[entry])
                        uncertaintyType = '+|-'
                    else:
                        uncertainties = {}
                    # should be entry.*
                    shortDesc = "Fitted to {0} distances.\n".format(
                        self.groupCounts[entry][0])
                    longDesc = "\n".join(self.groupComments[entry])
                    distances_dict = {key: distance for key, distance in zip(
                        distance_keys, self.groupValues[entry])}
                    uncertainties_dict = {key: distance for key, distance in zip(
                        distance_keys, uncertainties)}

                    entry.data = DistanceData(
                        distances=distances_dict, uncertainties=uncertainties_dict)
                    entry.shortDesc = shortDesc
                    entry.longDesc = longDesc
                else:
                    entry.data = DistanceData()
                    entry.longDesc = ''
        logging.info("Finished Updating Entries for {}\n".format(self.family))
        return

    def save_database(self, path=None):
        """
        Saves self.database of this instance to path if privided.

        If path not provided, appends TS_groups.py to self.path
        """
        if path is None and self.path is None:
            logging.error("Need path to save output")
        elif path is None:
            path = os.join(self.path, 'TS_groups.py')

        self.database.saveTransitionStateGroups(path)
        logging.info('Saved {} Database to: {}'.format(self.family, path))
        return
