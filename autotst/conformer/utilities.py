#!/usr/bin/python
# -*- coding: utf-8 -*-

################################################################################
#
#   AutoTST - Automated Transition State Theory
#
#   Copyright (c) 2015-2018 Prof. Richard H. West (r.west@northeastern.edu)
#
#   Permission is hereby granted, free of charge, to any person obtaining a
#   copy of this software and associated documentation files (the 'Software'),
#   to deal in the Software without restriction, including without limitation
#   the rights to use, copy, modify, merge, publish, distribute, sublicense,
#   and/or sell copies of the Software, and to permit persons to whom the
#   Software is furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#   FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#   DEALINGS IN THE SOFTWARE.
#
################################################################################

import os
import sys
import logging
FORMAT = "%(filename)s:%(lineno)d %(funcName)s %(levelname)s %(message)s"
logging.basicConfig(format=FORMAT, level=logging.INFO)

import itertools
import random
import numpy as np
from numpy import array
import pandas as pd
import cPickle as pickle


# do this before we have a chance to import openbabel!
import rdkit, rdkit.Chem.rdDistGeom, rdkit.DistanceGeometry

from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import rdBase

from rmgpy.molecule import Molecule
from rmgpy.species import Species
from rmgpy.reaction import Reaction

from autotst.molecule import *
from autotst.reaction import *

from ase.calculators.morse import *
from ase.calculators.dftb import *
from ase.calculators.lj import *
from ase.calculators.emt import *


def create_initial_population(multi_object, delta=30, population_size=200):
    """
    A function designed to take a multi_molecule, multi_rxn or multi_ts object
    and create an initial population of conformers.

    :param:
     multi_object: a multi_molecule, multi_ts, or multi_rxn object
     calc: an ASE calculator. If none is chosen, an EMT() calculator will be used
     delta: the step size between possible dihedral angles in degrees.
     population_size: the number of individuals to be used for the population

    :return:
     df: a DataFrame of the results sorted by the lowest energy conformers
    """
    logging.info("Creating initial population of {} individuals from random guesses".format(population_size))

    df = None

    possible_dihedrals = np.arange(0, 360, delta)
    population = []

    if "AutoTST_Molecule" in str(multi_object.__class__):
        logging.info("The object given is a `Multi_Molecule` object")

        torsion_object = multi_object

        for indivudual in range(population_size):
            dihedrals = []
            for torsion in torsion_object.torsions:
                dihedral = np.random.choice(possible_dihedrals)
                dihedrals.append(dihedral)
                i, j, k, l = torsion.indices
                right_mask = torsion.right_mask

                torsion_object.ase_molecule.set_dihedral(
                    a1=i,
                    a2=j,
                    a3=k,
                    a4=l,
                    angle=float(dihedral),
                    mask=right_mask
                )

            torsion_object.update_from_ase_mol()

            e = torsion_object.ase_molecule.get_potential_energy()

            population.append([e] + dihedrals)

    elif "AutoTST_Reaction" in str(multi_object.__class__):
        logging.info("The object given is a `Multi_Reaction` object")

        torsion_object = multi_object.ts

        for i in range(population_size):
            dihedrals = []

            for torsion in torsion_object.torsions:
                dihedral = np.random.choice(possible_dihedrals)
                dihedrals.append(dihedral)
                i, j, k, l = torsion.indices
                right_mask = torsion.right_mask

                torsion_object.ase_ts.set_dihedral(
                    a1=i,
                    a2=j,
                    a3=k,
                    a4=l,
                    angle=float(dihedral),
                    mask=right_mask
                )

            torsion_object.update_from_ase_ts()

            e = torsion_object.ase_ts.get_potential_energy()

            population.append([e] + dihedrals)

    elif "AutoTST_TS" in str(multi_object.__class__):
        logging.info("The object given is a `Multi_TS` object")

        torsion_object = multi_object

        for i in range(population_size):
            dihedrals = []

            for torsion in torsion_object.torsions:
                dihedral = np.random.choice(possible_dihedrals)
                dihedrals.append(dihedral)
                i, j, k, l = torsion.indices
                right_mask = torsion.right_mask

                torsion_object.ase_ts.set_dihedral(
                    a1=i,
                    a2=j,
                    a3=k,
                    a4=l,
                    angle=float(dihedral),
                    mask=right_mask
                )

            torsion_object.update_from_ase_ts()

            e = torsion_object.ase_ts.get_potential_energy()

            population.append([e] + dihedrals)

    if len(population) > 0:
        logging.info("Creating a dataframe of the initial population")
        df = pd.DataFrame(population)
        columns = ["Energy"]
        for i in range(len(torsion_object.torsions)):
            columns = columns + ["Torsion " + str(i)]
        df.columns = columns
        df = df.sort_values("Energy")

    return df


def select_top_population(df=None, top_percent=0.30):
    """
    :param:
     df: a DataFrame of a population of torsions with columns of `Energy` and `Torsion N`
     top_percent: a float of the top percentage of the population requested

    :return:
     top: a DataFrame containing the top percentage of the population
    """

    logging.info("Selecting the top population")
    assert "Energy" in df.columns
    df.sort_values("Energy")
    population_size = df.shape[0]
    top_population = population_size * top_percent
    top = df.iloc[:int(top_population), :]

    return top
