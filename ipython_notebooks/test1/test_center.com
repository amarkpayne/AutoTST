%nprocshared=20
%mem=5GB
#p hf/6-31g* opt=(ts,calcfc,noeigentest,ModRedun)

Gaussian input prepared by ASE

0 2
O                -2.4967826965        1.0322099368       -2.1032186176
O                -1.7932442358        0.2704035377       -2.9845287717
C                 0.5030953844        1.1741327338       -1.0436859107
C                 0.7835676770        0.1237845986       -0.2290253170
C                -0.5719244752        2.1500681810       -0.8907011320
C                 1.9386248972       -0.7979089569       -0.5323230440
C                 0.0215036408       -0.2077810309        1.0296878971
H                -1.5845471063       -0.5156799933       -2.4929974674
H                 1.1111229814        1.2909096215       -1.9251340655
H                -1.6172797787        1.7128592091       -1.5499462150
H                -0.3922273554        3.0935041152       -1.3863777095
H                -0.9740426620        2.2870836227        0.1012531178
H                 2.4550673944       -0.5146468242       -1.4417808218
H                 2.6609188996       -0.7921071634        0.2810953363
H                 1.5994196666       -1.8258195867       -0.6422335169
H                -0.8485082094        0.4161935239        1.1796226627
H                -0.3141444933       -1.2419186492        1.0073277980
H                 0.6638291846       -0.1064132709        1.9017877897

2 3 F
2 4 F
2 6 F
2 7 F
2 8 F
2 9 F
2 11 F
2 12 F
2 13 F
2 14 F
2 15 F
2 16 F
2 17 F
2 18 F
3 4 F
3 6 F
3 7 F
3 8 F
3 9 F
3 11 F
3 12 F
3 13 F
3 14 F
3 15 F
3 16 F
3 17 F
3 18 F
4 6 F
4 7 F
4 8 F
4 9 F
4 11 F
4 12 F
4 13 F
4 14 F
4 15 F
4 16 F
4 17 F
4 18 F
6 7 F
6 8 F
6 9 F
6 11 F
6 12 F
6 13 F
6 14 F
6 15 F
6 16 F
6 17 F
6 18 F
7 8 F
7 9 F
7 11 F
7 12 F
7 13 F
7 14 F
7 15 F
7 16 F
7 17 F
7 18 F
8 9 F
8 11 F
8 12 F
8 13 F
8 14 F
8 15 F
8 16 F
8 17 F
8 18 F
9 11 F
9 12 F
9 13 F
9 14 F
9 15 F
9 16 F
9 17 F
9 18 F
11 12 F
11 13 F
11 14 F
11 15 F
11 16 F
11 17 F
11 18 F
12 13 F
12 14 F
12 15 F
12 16 F
12 17 F
12 18 F
13 14 F
13 15 F
13 16 F
13 17 F
13 18 F
14 15 F
14 16 F
14 17 F
14 18 F
15 16 F
15 17 F
15 18 F
16 17 F
16 18 F
17 18 F
