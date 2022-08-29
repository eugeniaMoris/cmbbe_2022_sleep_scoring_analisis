#Clasificacion de estapas de sueño utilizando wivelets y el dataset de sleep-edf
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, confusion_matrix, multilabel_confusion_matrix, confusion_matrix
from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit
from sklearn.decomposition import PCA
from sklearn.svm import SVC
import metrics
import read_EDF_data_per_sj 
import balance_data
import matplotlib.pyplot as plt
import numpy as np
import pywt
import mne
import random
import seaborn as sns
import copy

def get_position(lst, item):
    return [i for i, x in enumerate(lst) if x == item]

def normalize_mat(mat):
    row,col= mat.shape
    media = np.empty(col)
    std = np.empty(col)
    new_mat = np.empty((row,col))
    #print('columna: ', col)
    for i in range(col):
        media[i] = np.mean(mat[:,i])
        std[i] = np.std(mat[:,i])
        #print('MEDIA Y DESVIO: ', media[i], std[i])

        for j in range(row):
            #print(mat[j,i])
            if std[i] == 0:
                aux = mat[j,i]
            else:
                aux = (mat[j,i] - media[i])/std[i]
            new_mat[j,i]=aux
    return new_mat, media, std

def get_new_data(epochs):
    #tener en cuenta que no van a tener el mismo orden
    #for e in epochs:
    aux = []
    #MODELO 1
    s1= epochs['Sleep stage 1']
    s2= epochs['Sleep stage 2']


    aux.insert(len(aux),s1)
    aux.insert(len(aux),s2)
    #print('tipos ', type(s1))
    return mne.concatenate_epochs(aux)

def train_data(epochs, index, subjects, modelo, wavelet, n_features, rus, n_trees):
    
    valid = epochs[index]
    print('SUJETO: ', subjects[index])
    epochs.pop(index)
    all_epochs = mne.concatenate_epochs(epochs)

    #BALANCEO DE CLASES - SE REDUCE CLASE 2
    all_epochs = balance_data.balance_epochs(all_epochs,rus)
    labels = all_epochs.events[:, -1]

    #elimino la tercer clase
    if modelo == 2:
        all_epochs = get_new_data(all_epochs)
        labels = all_epochs.events[:,-1]
        #valid = get_new_data(valid)
        

    #print('epochs: ', all_epochs)

    train_matrix= []
    for e in all_epochs:
        
        #MODELO 1
        CA, CD1, CD2, CD3 = pywt.wavedec(e[0,:],wavelet,level=3)
        if modelo == 1:
            CA = np.append(CA,CD2)
        elif modelo == 2:
            print(CA)
            CA = np.append(CA,CD1)
        print('TAMAÑO DE CA: ', len(CA))



        train_matrix.append(CA)

    train_matrix = np.array(train_matrix)

    #ESTANDARIZACION ENTRENAMIEO
    train_norm, medias, stds = normalize_mat(train_matrix)

    #PCA
    pca = PCA(n_components= n_features)
    train_norm = pca.fit_transform(train_norm)

    #SEPARADO EN DOS MODELOS, PRIMERO SE SEPARA LA CLASE 3
    clf1 = RandomForestClassifier(n_estimators=n_trees, random_state=random.seed(1234))
    first_labels= labels.copy()

    if modelo == 1:
        first_labels[first_labels==3]=2 #primer modelo


    clf1.fit(train_norm,first_labels)

    valid_wavelet = []
    y_valid = valid.events[:,-1]

    for v in valid:

        #MODELO 1
        CA, CD1, CD2, CD3 = pywt.wavedec(v[0,:],wavelet,level=3)
        if modelo == 1:
            CA = np.append(CA,CD2)
        elif modelo == 2:
            CA = np.append(CA,CD1)

        
        #ESTADARIZACION VALIDACION
        for i in range(len(CA)):
            CA[i]= (CA[i]-medias[i])/stds[i]
        valid_wavelet.insert(len(valid_wavelet), CA)

    valid_matrix = np.array(valid_wavelet)
    
    #PCA
    valid_matrix=pca.transform(valid_matrix)
    
    y_predict_1 = clf1.predict(valid_matrix)


    y_predict = y_predict_1
    if modelo == 1:
        y_valid[y_valid==3]=2 #para entrenar primer modelos



    return y_predict, y_valid

def train(epochs,modelo, wavelet, n_features, rus, n_trees):

    all_epochs = mne.concatenate_epochs(epochs)

    #BALANCEO DE CLASES - SE REDUCE CLASE 2
    all_epochs = balance_data.balance_epochs(all_epochs,rus)
    labels = all_epochs.events[:, -1]

    #elimino la tercer clase
    if modelo == 2:
        all_epochs = get_new_data(all_epochs)
        labels = all_epochs.events[:,-1]

    train_matrix= []
    for e in all_epochs:
        
        #MODELO 1
        CA, CD1, CD2, CD3 = pywt.wavedec(e[0,:],wavelet,level=3)
        if modelo == 1:
            CA = np.append(CA,CD2)
        elif modelo == 2:
            
            CA = np.append(CA,CD1)
            #CA= float(CA)
            #print(CA)


        #print('SHAPE CA: ', CA.shape)
        #CA= np.ravel(CA)
        train_matrix.append(CA)

    train_matrix = np.array(train_matrix)

    #ESTANDARIZACION ENTRENAMIEO
    train_norm, medias, stds = normalize_mat(train_matrix)

    #PCA
    pca = PCA(n_components= n_features)
    train_norm = pca.fit_transform(train_norm)

    #SEPARADO EN DOS MODELOS, PRIMERO SE SEPARA LA CLASE 3
    clf1 = RandomForestClassifier(n_estimators=n_trees, random_state=random.seed(1234))
    first_labels= labels.copy()

    if modelo == 1:
        first_labels[first_labels==3]=2 #primer modelo


    clf1.fit(train_norm,first_labels)

    return clf1, medias, stds, pca

def predict_test(model1,model2,test,media1,media2,std1,std2,pca1,pca2,w1,w2):
    test_wavelet1 = []
    test_wavelet2 = []

    y_test = test.events[:,-1]

    for t in test:
        #MODELO 1
        w1CA, w1CD1, w1CD2, w1CD3 = pywt.wavedec(t[0,:],w1,level=3)
        w2CA, w2CD1, w2CD2, w2CD3 = pywt.wavedec(t[0,:],w2,level=3)

        CAM1 = np.append(w1CA,w1CD2)
        CAM2 = np.append(w2CA,w2CD1)

        
        #ESTADARIZACION VALIDACION
        for i in range(len(CAM1)):
            if std1[i] == 0:
                CAM1[i] = CAM1[i]
            else:
                CAM1[i] = (CAM1[i] - media1[i])/std1[i]
            #CAM1[i]= (CAM1[i]-media1[i])/std1[i]
        test_wavelet1.insert(len(test_wavelet1), CAM1)

        for i in range(len(CAM2)):
            if std2[i] == 0:
                CAM2[i] = CAM2[i]
            else:
                CAM2[i] = (CAM2[i] - media2[i])/std2[i]
            #CAM2[i]= (CAM2[i]-media2[i])/std2[i]
        test_wavelet2.insert(len(test_wavelet2), CAM2)

    test_matrix1 = np.array(test_wavelet1)
    test_matrix2 = np.array(test_wavelet2)

    #PCA
    test_matrix1=pca1.transform(test_matrix1)
    test_matrix2=pca2.transform(test_matrix2)
    
    y_predict_1 = model1.predict(test_matrix1)
    y_predict_2 = model2.predict(test_matrix2)

    y_predict = np.empty((len(y_predict_1)))

    #MODELO 1
    for i in range(len(y_predict_1)):
        if y_predict_1[i] == 4:
            y_predict[i] = 4
        if (y_predict_1[i] == 2) and (y_predict_2[i] == 3):
            y_predict[i] = 3
        if (y_predict_1[i] == 2) and (y_predict_2[i] == 2):
            y_predict[i] = 2


    return y_predict,y_test


#MODELO 1
# #class 3 vs 1,2 y class 1 vs 2
wavelet_1 = 'bior1.1'
n_features_1 = 350
rus_1 =45
n_trees_1 = 150
wavelet_2 = 'rbio1.1'
n_features_2 = 250
rus_2 =20
n_trees_2 = 300



wavelet_family=['MODEL 1']

epochs, subjects,_= read_EDF_data_per_sj.get_eeg_data(0,40)
train_epochs = epochs[:14]

epochs, subjects,_= read_EDF_data_per_sj.get_eeg_data(0,40)
test_epochs = epochs[14:]

#datos de test
#test_epochs = epochs[14:]
#test_sj = subjects[14:]
#test_epochs = mne.concatenate_epochs(test_epochs)

for family in wavelet_family:

    acc = np.empty(len(test_epochs))
    f1 = np.empty(len(test_epochs))    
    prec = np.empty(len(test_epochs))    
    recall = np.empty(len(test_epochs))

    acc_s1 = np.empty(len(test_epochs))
    prec_s1 = np.empty(len(test_epochs))
    recall_s1 = np.empty(len(test_epochs))
    f1_s1 = np.empty(len(test_epochs))

    acc_s2 = np.empty(len(test_epochs))
    prec_s2 = np.empty(len(test_epochs))
    recall_s2 = np.empty(len(test_epochs))
    f1_s2 = np.empty(len(test_epochs))

    acc_s3 = np.empty(len(test_epochs))
    prec_s3 = np.empty(len(test_epochs))
    recall_s3 = np.empty(len(test_epochs))
    f1_s3 = np.empty(len(test_epochs))

    #for index in range(len(train_epochs)):
    
    #for index in range(len(train_data)):

        #print('INDEX: ', index)
        #y_predict_1, y_valid = train_data(copy.deepcopy(train_epochs),index,train_sj,1,wavelet_1,n_features_1,rus_1,n_trees_1)
        #y_predict_2, y_valid = train_data(copy.deepcopy(train_epochs),index,subjects,2,wavelet_2,n_features_2,rus_2,n_trees_2)
    
    index=0
    model1, m1, std1, pca1 = train(copy.deepcopy(train_epochs),1,wavelet_1,n_features_1,rus_1,n_trees_1)
    model2, m2, std2, pca2 = train(copy.deepcopy(train_epochs),2,wavelet_2,n_features_2,rus_2,n_trees_2)
    
    for t in test_epochs:

        y_pred, y_test =predict_test(model1,model2, t, m1, m2, std1, std2, pca1, pca2,wavelet_1,wavelet_2)

        acc[index] = (accuracy_score(y_test,y_pred))
        f1[index] = (f1_score(y_test,y_pred,average='macro'))
        prec[index] = (precision_score(y_test,y_pred,average='macro'))
        recall[index] = (recall_score(y_test,y_pred,average='macro'))

        S1, S2, S3 = multilabel_confusion_matrix(y_test, y_pred)
        #S1, S2 = multilabel_confusion_matrix(y_valid, y_predict_2)

        acc_s1[index], f1_s1[index] = metrics.get_metrics(S1,1)
        acc_s2[index], f1_s2[index] = metrics.get_metrics(S2,1)
        acc_s3[index], f1_s3[index] = metrics.get_metrics(S3,1)
        index = index+1

        print(confusion_matrix(y_true=y_test, y_pred=y_pred))

    print ('Accuracy- mean: ', np.mean(acc), ' std: ', np.std(acc))
    print ('F1 Score - mean: ', np.mean(f1), ' std: ', np.std(f1))

    print ('Stage 1: Accuracy- ', np.mean(acc_s1), ' Fscore: ', np.mean(f1_s1))
    print ('Stage 2: Accuracy- ', np.mean(acc_s2), ' Fscore: ', np.mean(f1_s2))
    print ('Stage 3: Accuracy- ', np.mean(acc_s3), ' Fscore: ', np.mean(f1_s3))



    data= []
    data.insert(len(data), f1_s1)
    data.insert(len(data), f1_s2)
    data.insert(len(data), f1_s3)

    f = open(str(family) + "-.txt", "w")
    f.write(str(family) + '\n')
    f.write('Accuracy- mean: ' + str(np.mean(acc)) +'\n')
    f.write('F1 Score - mean: ' + str(np.mean(f1)) +'\n')

    f.write('Stage 1: Accuracy- '+ str(np.mean(acc_s1))+ ' Fscore: '+ str(np.mean(f1_s1))+'\n')
    f.write('Stage 2: Accuracy- '+ str(np.mean(acc_s2))+ ' Fscore: '+ str(np.mean(f1_s2))+'\n')
    f.write('Stage 3: Accuracy- '+ str(np.mean(acc_s3))+ ' Fscore: '+ str(np.mean(f1_s3))+'\n')
    f.write('Data: '+ 'f1: '+ str(f1_s1) +'f2 '+ str(f1_s2) +'f3'+ str(f1_s3))
    f.close()


#print('f1: ',f1_s1,'f2 ', f1_s2,'f3', f1_s3)

# sns.set_theme(style="whitegrid")
# ax= sns.violinplot(data=data,palette='colorblind')
# ax = sns.swarmplot(data=data, color="white")
# plt.show()
