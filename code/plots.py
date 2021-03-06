import pandas as pd
import numpy as np
import tqdm
import torch
import math
from torch_geometric.data import Data, DataListLoader, Batch
from torch.utils.data import random_split
import os.path as osp
import matplotlib.pyplot as plt
from graph_data import GraphDataset
import sys
from models import EdgeNet
from sklearn.metrics import mean_squared_error
from scipy.stats import iqr

device = 'cuda:0'
batch_size = 4

def collate(items):
    l = sum(items, [])
    return Batch.from_data_list(l)

def get_data():
    gdata = GraphDataset(root='/anomalyvol/data/gnn_node_global_merge', bb=0)
    fulllen = len(gdata)
    tv_frac = 0.10
    tv_num = math.ceil(fulllen*tv_frac)
    torch.manual_seed(0)
    train_dataset, valid_dataset, test_dataset = random_split(gdata, [fulllen-2*tv_num,tv_num,tv_num])

    train_loader = DataListLoader(train_dataset, batch_size=batch_size, pin_memory=True, shuffle=True)
    train_loader.collate_fn = collate
    valid_loader = DataListLoader(valid_dataset, batch_size=batch_size, pin_memory=True, shuffle=False)
    valid_loader.collate_fn = collate
    test_loader = DataListLoader(test_dataset, batch_size=batch_size, pin_memory=True, shuffle=False)
    test_loader.collate_fn = collate
    
    train_samples = len(train_dataset)
    valid_samples = len(valid_dataset)
    test_samples = len(test_dataset)

    return train_loader, valid_loader, test_loader, train_samples, valid_samples, test_samples

def get_model(model_name):
    # specific for gnn_geom for now
    model = EdgeNet().to(device)
    modpath = osp.join('/anomalyvol/models/',model_name+'.best.pth')
    try:
        model.load_state_dict(torch.load(modpath))
    except:
        sys.exit("Model not found at: " + modpath)
    
    return model

# helper for appending 3 lists
def in_out_diff_append(diff, output, inputs, i, ft_idx, output_x, input_x):
    diff.append(((output_x[i][:,ft_idx]-input_x[i][:,ft_idx])/input_x[i][:,ft_idx]).flatten())
    output.append(output_x[i][:,ft_idx].flatten())
    inputs.append(input_x[i][:,ft_idx].flatten())

def in_out_diff_concat(diff, output, inputs):
    diff = np.concatenate(diff)
    output = np.concatenate(output)
    inputs = np.concatenate(inputs)
    return [diff, output, inputs]

def make_hists(diff, output, inputs, bin1, feat, feat_diff, model_name):
    plt.figure(figsize=(6,4.4))
    plt.hist(inputs, bins=bin1,alpha=0.5, label='Input')
    plt.hist(output, bins=bin1,alpha=0.5, label='Output')
    plt.legend()
    plt.xlabel(feat, fontsize=16)
    plt.ylabel('Particles', fontsize=16)
    plt.tight_layout()
    plt.savefig('figures/' + model_name + '_' + feat[:-6] + '.pdf')
    
    plt.figure(figsize=(6,4.4))
    plt.hist(diff, bins=np.linspace(-2, 2, 101))
    plt.xlabel(feat_diff, fontsize=16)
    plt.ylabel('Particles', fontsize=16)
    plt.tight_layout()
    plt.savefig('figures/' + model_name + '_' + feat[:-6] + '_diff.pdf')

def gen_plots(model_name):
    model = get_model(model_name)
    train_loader, valid_loader, test_loader, train_samples, valid_samples, test_samples = get_data()

    input_x = []
    output_x = []
    t = tqdm.tqdm(enumerate(test_loader), total=test_samples/batch_size)
    for i, data in t:
        data.to(device)
        input_x.append(data.x.cpu().numpy())
        output_x.append(model(data).cpu().detach().numpy())

    diff_px = []
    output_px = []
    input_px = []
    diff_py = []
    output_py = []
    input_py = []
    diff_pz = []
    output_pz = []
    input_pz = []
    diff_e = []
    output_e = []
    input_e = []

    # get output in readable format
    for i in range(len(input_x)):
        in_out_diff_append(diff_px, output_px, input_px, i, 0, output_x, input_x)
        in_out_diff_append(diff_py, output_py, input_py, i, 1, output_x, input_x)
        in_out_diff_append(diff_pz, output_pz, input_pz, i, 2, output_x, input_x)
        in_out_diff_append(diff_e, output_e, input_e, i, 3, output_x, input_x)

    # remove extra brackets
    diff_px, output_px, input_px = in_out_diff_concat(diff_px, output_px, input_px)
    diff_py, output_py, input_py = in_out_diff_concat(diff_py, output_py, input_py)
    diff_pz, output_pz, input_pz = in_out_diff_concat(diff_pz, output_pz, input_pz)
    diff_e, output_e, input_e = in_out_diff_concat(diff_e, output_e, input_e)
    
    diff_px = diff_px[np.logical_not(np.isnan(diff_px))]
    diff_py = diff_py[np.logical_not(np.isnan(diff_py))]
    diff_pz = diff_pz[np.logical_not(np.isnan(diff_pz))]
    diff_e = diff_e[np.logical_not(np.isnan(diff_e))]

    # make plots
    feat = '$p_x$ [GeV]'
    feat_diff = '$(p_x^{reco.}  - p_x^{true})/p_x^{true}$'
    bins = np.linspace(-20, 20, 101)
    make_hists(diff_px, output_px, input_px, bins, feat, feat_diff, model_name)
    # quantitative info
    ft_idx = 0
    print(feat)
    print("mean: " + str(np.mean(diff_px)))
    result = iqr(diff_px,rng=(16,84)) / 2
    print('iqr: ' + str(result))

    feat = '$p_y$ [GeV]'
    feat_diff = '$(p_y^{reco.}  - p_y^{true})/p_y^{true}$'
    make_hists(diff_py, output_py, input_py, bins, feat, feat_diff, model_name)
    # quantitative info
    ft_idx = 1
    print(feat)
    print("mean: " + str(np.mean(diff_py)))
    result = iqr(diff_py,rng=(16,84)) / 2
    print('iqr: ' + str(result))

    feat = '$p_z$ [GeV]'
    feat_diff = '$(p_z^{reco.}  - p_z^{true})/p_z^{true}$'
    make_hists(diff_pz, output_pz, input_pz, bins, feat, feat_diff, model_name)
    # quantitative info
    ft_idx = 2
    print(feat)
    print("mean: " + str(np.mean(diff_pz)))
    result = iqr(diff_pz,rng=(16,84)) / 2
    print('iqr: ' + str(result))

    feat = '$E$ [GeV]'
    feat_diff = '$(E^{reco.}  - E^{true})/E^{true}$'
    bins = np.linspace(-5, 35, 101)
    make_hists(diff_e, output_e, input_e, bins, feat, feat_diff, model_name)
    # quantitative info
    ft_idx = 3
    print(feat)
    print("mean: " + str(np.mean(diff_e)))
    result = iqr(diff_e,rng=(16,84)) / 2
    print('iqr: ' + str(result))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, help="name of model file", required=True)
    args = parser.parse_args()
    
    gen_plots(args.model_name)
