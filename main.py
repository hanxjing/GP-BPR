# coding=utf-8
from GPBPR import GPBPR
import torch

from torch.utils.data import TensorDataset,DataLoader
from torch import load, sigmoid, cat, rand, bmm, mean, matmul
from torch.nn.functional import logsigmoid
from torch.nn.init import uniform_

from torch.optim import Adam
from sys import argv

"""
    my_config is a dict which contains necessary filepath in trainning and evaluating GP-BPR model

    visual_features is the output of last avgpool in resnet50 of torchvision, obtained by 

    textural_features is the input of word embeding layer

    embedding_matrix is the word embedding vector from nwjc2vec. Missing word initialed as zero vector 
"""

my_config = {
    "visual_features_dict": "./feat/visualfeatures",
    "textural_idx_dict": "./feat/textfeatures",
    "textural_embedding_matrix": "./feat/smallnwjc2vec",
    "train_data": r"./data/train.csv",
    "valid_data": r"./data/valid.csv",
    "test_data": r"./data/test.csv",
    "model_file": r"./model/GPBPR.model",
}
 
def load_csv_data(train_data_path):
    result = []
    with open(train_data_path,'r') as fp:
        for line in fp:
            t = line.strip().split(',')
            t = [int(i) for i in t]
            result.append(t)
    return result
def load_embedding_weight(device):
    jap2vec = torch.load(my_config['textural_embedding_matrix'])
    embeding_weight = []
    for jap, vec in jap2vec.items():
        embeding_weight.append(vec.tolist())
    embeding_weight.append(torch.zeros(300))
    embedding_weight = torch.tensor(embeding_weight, device=device)
    return embedding_weight


def trainning(model, mode, train_data_loader, device, visual_features, text_features, opt):
    r"""
        using data from Args to train model

        Args:

            mode: -

            train_data_loader: mini-batch iteration

            device: device on which model train

            visual_features: look up table for item visual features

            text_features: look up table for item textural features

            opt: optimizer of model
    """
    model.train()
    model = model.to(device)
    for iteration,aBatch in enumerate(train_data_loader):

        output , outputweight = model.fit(aBatch[0], visual_features, text_features, weight=False)  
        # print(output.size())
        loss = (-logsigmoid(output)).sum() + 0.001*outputweight
        iteration += 1
        opt.zero_grad()
        loss.backward()
        opt.step()

def evaluating(model, mode, test_csv, visual_features, text_features):
    r"""
        using data from Args to train model

        Args:

            mode: -

            train_data_loader: mini-batch iteration

            test_csv: valid file or test file

            visual_features: look up table for item visual features

            text_features: look up table for item textural features
    """
    model.eval()
    testData = load_csv_data(test_csv)
    pos = 0
    batch_s = 100
    for i in range(0, len(testData), batch_s):
        data = testData[i:i+batch_s] if i+batch_s <=len(testData) else testData[i:]
        output = model.forward(data, visual_features, text_features)  
        
        pos += float(torch.sum(output.ge(0)))
    print( "evaling process: " , test_csv , model.epoch, pos/len(testData))

def F(mode ,hidden_dim, batch_size, device):
    print('loading top&bottom features')
    # torch.cuda.set_device("")
    train_data = load_csv_data(my_config['train_data'])

    visual_features = torch.load(my_config['visual_features_dict'], map_location= lambda a,b:a.cpu())
    
    text_features = torch.load(my_config['textural_idx_dict'], map_location= lambda a,b:a.cpu())

    try:
        print("loading model")
        gpbpr = load(my_config['model_file'], map_location=lambda x,y: x.cuda(device))
    except Exception as e:
        print(e)
        print('no module exists, created new one {}'.format(my_config['model_file']))
        embedding_weight = load_embedding_weight(device)
        item_set= set()
        user_set = set([str(i[0]) for i in train_data])
        for i in train_data:
            item_set.add(str(int(i[2])))
            item_set.add(str(int(i[3])))
        gpbpr = GPBPR(user_set = user_set, item_set = item_set, 
            embedding_weight=embedding_weight, uniform_value = 0.3).to(device)
    
    opt = Adam([
    {
        'params': gpbpr.parameters(),
        'lr': 0.001,
    }
    ])

    train_data = TensorDataset(torch.tensor(train_data, dtype=torch.int))
    train_loader = DataLoader(train_data, batch_size= batch_size,shuffle=True, drop_last=True)


    for i in range(40):

        # 这里是单个进程的训练
        trainning(gpbpr, mode, train_loader,device, visual_features, text_features, opt)
        
        
        gpbpr.epoch+=1
        torch.save(gpbpr, my_config['model_file'])

        evaluating(gpbpr,mode, my_config['valid_data'],  visual_features, text_features,)
        evaluating(gpbpr,mode, my_config['test_data'],  visual_features, text_features,)


if __name__ == "__main__":

    # "cpu" or "cuda:x" x is GPU index like (0,1,2,3,)
    import os
    try:
        os.mkdir('./model')
    except Exception: pass
    F(mode = 'final', hidden_dim = 512, batch_size = 256, device = 0)
