import torch
import numpy as np
import torch.utils.data
from lib.normalization import NScaler, MinMax01Scaler, MinMax11Scaler, StandardScaler, ColumnMinMaxScaler


# For PEMS03/04/07/08 Datasets
def get_dataloader(args, normalizer = 'std', tod=False, dow=False, weather=False, single=True):
    #load raw st dataset
    data = load_st_dataset(args.dataset)        # B, N, D
    #normalize st data
    data, scaler = normalize_dataset(data, normalizer, args.column_wise)
    #spilit dataset by days or by ratio
    if args.test_ratio > 1:
        data_train, data_val, data_test = split_data_by_days(data, args.val_ratio, args.test_ratio)
    else:
        data_train, data_val, data_test = split_data_by_ratio(data, args.val_ratio, args.test_ratio)
    #add time window
    x_tra, y_tra = Add_Window_Horizon(data_train, args.lag, args.horizon, single)
    x_val, y_val = Add_Window_Horizon(data_val, args.lag, args.horizon, single)
    x_test, y_test = Add_Window_Horizon(data_test, args.lag, args.horizon, single)
    print('Train: ', x_tra.shape, y_tra.shape)
    print('Val: ', x_val.shape, y_val.shape)
    print('Test: ', x_test.shape, y_test.shape)
    ##############get dataloader######################
    train_dataloader = data_loader(x_tra, y_tra, args.batch_size, shuffle=True, drop_last=True)
    if len(x_val) == 0:
        val_dataloader = None
    else:
        val_dataloader = data_loader(x_val, y_val, args.batch_size, shuffle=False, drop_last=True)
    test_dataloader = data_loader(x_test, y_test, args.batch_size, shuffle=False, drop_last=False)
    return train_dataloader, val_dataloader, test_dataloader, scaler


# For PEMS-Bay and METR-LA Datasets
def get_dataloader_meta_la(args, normalizer='std', tod=False, dow=False, weather=False, single=True):
    data = {}
    for category in ['train', 'val', 'test']:
        cat_data = np.load(os.path.join("./dataset", args.dataset, category + '.npz'))
        data['x_' + category] = cat_data['x'] # [B, T, N, 2]
        data['y_' + category] = np.expand_dims(cat_data['y'][:, :, :, 0], axis=-1) # [B, T, N, 1]
        
    # data normalization method following DCRNN
    scaler = StandardScaler(mean=data['x_train'][..., 0].mean(), std=data['x_train'][..., 0].std())
    for category in ['train', 'val', 'test']:
        data['x_' + category][:, :, :, 0] = scaler.transform(data['x_' + category][:, :, :, 0])
    if not args.real_value:
        data['y_' + category][:, :, :, 0] = scaler.transform(data['y_' + category][:, :, :, 0])
    
    x_tra, y_tra = data['x_train'], data['y_train']
    x_val, y_val = data['x_val'], data['y_val']
    x_test, y_test = data['x_test'], data['y_test']

    print('Train: ', x_tra.shape, y_tra.shape)
    print('Val: ', x_val.shape, y_val.shape)
    print('Test: ', x_test.shape, y_test.shape)

    ##############get dataloader######################
    train_dataloader = data_loader(x_tra, y_tra, args.batch_size, shuffle=True, drop_last=True)
    if len(x_val) == 0:
        val_dataloader = None
    else:
        val_dataloader = data_loader(x_val, y_val, args.batch_size, shuffle=False, drop_last=True)
    test_dataloader = data_loader(x_test, y_test, args.batch_size, shuffle=False, drop_last=False)
    
    return train_dataloader, val_dataloader, test_dataloader, scaler


def load_st_dataset(dataset):
    project_path = '/home/wbq/work/DSTCGCN/'
    
    if dataset == 'PEMS03':
        data_path = os.path.join(f'{project_path}/data/pems03.npz')
        data = np.load(data_path)['data'][:, :, 0]  #onley the first dimension, traffic flow data
    elif dataset == 'PEMS04':
        data_path = os.path.join(f'{project_path}/data/pems04.npz')
        data = np.load(data_path)['data'][:, :, 0]
    elif dataset == 'PEMS07':
        data_path = os.path.join(f'{project_path}/data/pems07.npz')
        data = np.load(data_path)['data'][:, :, 0]
    elif dataset == 'PEMS08':
        data_path = os.path.join(f'{project_path}/data/pems08.npz')
        data = np.load(data_path)['data'][:, :, 0]
    else:
        raise ValueError
    if len(data.shape) == 2:
        data = np.expand_dims(data, axis=-1)
    print('Load %s Dataset shaped: ' % dataset, data.shape, data.max(), data.min(), data.mean(), np.median(data))
    return data


def normalize_dataset(data, normalizer, column_wise=False):
    if normalizer == 'max01':
        if column_wise:
            minimum = data.min(axis=0, keepdims=True)
            maximum = data.max(axis=0, keepdims=True)
        else:
            minimum = data.min()
            maximum = data.max()
        scaler = MinMax01Scaler(minimum, maximum)
        data = scaler.transform(data)
        print('Normalize the dataset by MinMax01 Normalization')
    elif normalizer == 'max11':
        if column_wise:
            minimum = data.min(axis=0, keepdims=True)
            maximum = data.max(axis=0, keepdims=True)
        else:
            minimum = data.min()
            maximum = data.max()
        scaler = MinMax11Scaler(minimum, maximum)
        data = scaler.transform(data)
        print('Normalize the dataset by MinMax11 Normalization')
    elif normalizer == 'std':
        if column_wise:
            mean = data.mean(axis=0, keepdims=True)
            std = data.std(axis=0, keepdims=True)
        else:
            mean = data.mean()
            std = data.std()
        scaler = StandardScaler(mean, std)
        data = scaler.transform(data)
        print('Normalize the dataset by Standard Normalization')
    elif normalizer == 'None':
        scaler = NScaler()
        data = scaler.transform(data)
        print('Does not normalize the dataset')
    elif normalizer == 'cmax':
        #column min max, to be depressed
        #note: axis must be the spatial dimension, please check !
        scaler = ColumnMinMaxScaler(data.min(axis=0), data.max(axis=0))
        data = scaler.transform(data)
        print('Normalize the dataset by Column Min-Max Normalization')
    else:
        raise ValueError
    return data, scaler

def split_data_by_days(data, val_days, test_days, interval=60):
    '''
    :param data: [B, *]
    :param val_days:
    :param test_days:
    :param interval: interval (15, 30, 60) minutes
    :return:
    '''
    T = int((24*60)/interval)
    test_data = data[-T*test_days:]
    val_data = data[-T*(test_days + val_days): -T*test_days]
    train_data = data[:-T*(test_days + val_days)]
    return train_data, val_data, test_data

def split_data_by_ratio(data, val_ratio, test_ratio):
    data_len = data.shape[0]
    test_data = data[-int(data_len*test_ratio):]
    val_data = data[-int(data_len*(test_ratio+val_ratio)):-int(data_len*test_ratio)]
    train_data = data[:-int(data_len*(test_ratio+val_ratio))]
    return train_data, val_data, test_data

def data_loader(X, Y, batch_size, shuffle=True, drop_last=True):
    cuda = True if torch.cuda.is_available() else False
    TensorFloat = torch.cuda.FloatTensor if cuda else torch.FloatTensor
    X, Y = TensorFloat(X), TensorFloat(Y)
    data = torch.utils.data.TensorDataset(X, Y)
    dataloader = torch.utils.data.DataLoader(data, batch_size=batch_size,
                                             shuffle=shuffle, drop_last=drop_last)
    return dataloader


def Add_Window_Horizon(data, window=3, horizon=1, single=False):
    '''
    :param data: shape [B, ...]
    :param window:
    :param horizon:
    :return: X is [B, W, ...], Y is [B, H, ...]
    '''
    length = len(data)
    end_index = length - horizon - window + 1
    X = []      #windows
    Y = []      #horizon
    index = 0
    if single:
        while index < end_index:
            X.append(data[index:index+window])
            Y.append(data[index+window+horizon-1:index+window+horizon])
            index = index + 1
    else:
        while index < end_index:
            X.append(data[index:index+window])
            Y.append(data[index+window:index+window+horizon])
            index = index + 1
    X = np.array(X)
    Y = np.array(Y)
    return X, Y

if __name__ == '__main__':
    from data.load_raw_data import Load_Sydney_Demand_Data
    path = '../data/1h_data_new3.csv'
    data = Load_Sydney_Demand_Data(path)
    print(data.shape)
    X, Y = Add_Window_Horizon(data, horizon=2)
    print(X.shape, Y.shape)



if __name__ == '__main__':
    import argparse
    #MetrLA 207; BikeNYC 128; SIGIR_solar 137; SIGIR_electric 321
    DATASET = 'SIGIR_electric'
    if DATASET == 'MetrLA':
        NODE_NUM = 207
    elif DATASET == 'BikeNYC':
        NODE_NUM = 128
    elif DATASET == 'SIGIR_solar':
        NODE_NUM = 137
    elif DATASET == 'SIGIR_electric':
        NODE_NUM = 321
    parser = argparse.ArgumentParser(description='PyTorch dataloader')
    parser.add_argument('--dataset', default=DATASET, type=str)
    parser.add_argument('--num_nodes', default=NODE_NUM, type=int)
    parser.add_argument('--val_ratio', default=0.1, type=float)
    parser.add_argument('--test_ratio', default=0.2, type=float)
    parser.add_argument('--lag', default=12, type=int)
    parser.add_argument('--horizon', default=12, type=int)
    parser.add_argument('--batch_size', default=64, type=int)
    args = parser.parse_args()
    train_dataloader, val_dataloader, test_dataloader, scaler = get_dataloader(args, normalizer = 'std', tod=False, dow=False, weather=False, single=True)