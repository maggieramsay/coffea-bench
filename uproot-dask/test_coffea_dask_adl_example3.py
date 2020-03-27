# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.3.2
# ---

# Run this cell if you do not have coffea installed (e.g. on SWAN with LCG 96Python3 stack)
# (for .py version -> next line should be commented since they are converted to ipybn via jupytext)
# !pip install --user --upgrade coffea
# Preparation for testing
# !pip install --user --upgrade ipytest
# !pip install --user --upgrade pytest-benchmark


if hasattr(__builtins__,'__IPYTHON__'):
    import os
    import ipytest
    ipytest.config(rewrite_asserts=True, magics=True)
    __file__ = 'test_coffea_dask_adl_example3.ipynb'
    # Run this cell before establishing spark connection <<<<< IMPORTANT
    os.environ['PYTHONPATH'] = os.environ['PYTHONPATH'] + ':' + '/usr/local/lib/python3.6/site-packages'
    os.environ['PATH'] = os.environ['PATH'] + ':' + '/eos/user/o/oshadura/.local/bin'


import psutil
import pytest

from coffea import hist
from coffea.analysis_objects import JaggedCandidateArray
import coffea.processor as processor
import numpy as np

from dask.distributed import Client

fileset = {
    'Jets with pT > 20 and abs(eta) < 1': { 'files': ['root://eospublic.cern.ch//eos/root-eos/benchmark/Run2012B_SingleMu.root'],
             'treename': 'Events'
            }
}

# This program plots a per-event array (jet_pt) that has been masked to meet certain conditions (in this case, abs(jet eta) < 1).
class JetProcessor(processor.ProcessorABC):
    def __init__(self):
        self._columns = ['MET_pt', 'nJet', 'Jet_pt', 'Jet_eta', 'Jet_phi', 'Jet_mass']
        dataset_axis = hist.Cat("dataset", "")
        Jet_axis = hist.Bin("Jet_pt", "Jet_pt [GeV]", 100, 15, 60) 
        self._accumulator = processor.dict_accumulator({
            'Jet_pt': hist.Hist("Counts", dataset_axis, Jet_axis),
            'cutflow': processor.defaultdict_accumulator(int)
        })

    @property
    def columns(self):
        return self._columns
    
    @property
    def accumulator(self):
        return self._accumulator
    
    def process(self, df):
        output = self.accumulator.identity()
        
        dataset = df["dataset"]
        
        # JaggedCandidateArray bundles together keys from the TTree dict into a TLorentzVector, as well as any amount of additional keys. To refer to a TLorentzVector property, use "JCA"['p4']."property" or "JCA"."property"; to refer to extra keys, "JCA"["property"]
        jets = JaggedCandidateArray.candidatesfromcounts(
            df['nJet'],
            pt=df['Jet_pt'].content,
            eta=df['Jet_eta'].content,
            phi=df['Jet_phi'].content,
            mass=df['Jet_mass'].content,
            )

        output['cutflow']['all events'] += jets.size
        output['cutflow']['number of jets'] += jets.counts.sum()
        
        # We want jets with an abs(eta) < 1. Conditionals act on every value in an array in Coffea, so this is easy. Note that we must give one conditional statement as a time. Something of the sort '1 < jets['p4'].eta < 1' WILL return an error! An alternative to below is ((jets['p4'].eta < 1) & (jets['p4'].eta > -1)), but this feels unnecessarily long when numpy can be used. Also, don't use 'and', use '&'!
        eta_max = (np.absolute(jets['p4'].eta) < 1)
        # eta_max is a Boolean array, with True in the place of values where the condition is met, and False otherwise. We want to sum up all the Trues (=1) in each sublist, then sum up all the sublists to get the number of jets with pt > 20.
        output['cutflow']['abs(eta) < 1'] += eta_max.sum().sum()
            
        # We define good_jets as the actual jets we want to graph. We mask it with the jets that have abs(eta) < 1.
        good_jets = jets[eta_max]
        # good_jets is no longer a Boolean array, so we can't just sum up the True's. We count the amount of jets and sum that.
        output['cutflow']['final good jets'] += good_jets.counts.sum()
        
        output['Jet_pt'].fill(dataset=dataset, Jet_pt=good_jets['p4'].pt.flatten())
        return output

    def postprocess(self, accumulator):
        return accumulator


def test_dask_adlexample3(benchmark):
    @benchmark
    def dask_adlexample3():
        # Dask settings (two different cases)
        client = Client("t3.unl.edu:8786")
        #cluster = HTCondorCluster(cores=n_cores, memory="2GB",disk="1GB",dashboard_address=9998)
        #cluster.scale(jobs=5)
        #client = Client(cluster)
        cachestrategy = 'dask-worker'
        exe_args = {
            'client': client,
            'nano': True,
            'cachestrategy': cachestrategy,
            'savemetrics': True,
            'worker_affinity': True if cachestrategy is not None else False,
        }
        output = processor.run_uproot_job(fileset,
                                      treename = 'Events',
                                      processor_instance = JetProcessor(),
                                      executor = processor.dask_executor,
                                      executor_args = exe_args
                                      
        )
        return output 

if hasattr(__builtins__,'__IPYTHON__'):
    ipytest.run('-qq')
