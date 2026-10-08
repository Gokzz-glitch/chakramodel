#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb  4 18:18:57 2021

@author: sharib
For WL images only: Train-val-test data samples 
"""
 
import numpy as np 
import os
    

def detect_imgs(infolder, ext='.tif'):

    items = os.listdir(infolder)
    
    flist = []
    for names in items:
        if names.endswith(ext) or names.endswith(ext.upper()):
            flist.append(os.path.join(infolder, names))

    return np.sort(flist)

def detect_imgs_filesOnly(infolder, ext='.tif'):

    items = os.listdir(infolder)
    
    flist = []
    for names in items:
        if names.endswith(ext) or names.endswith(ext.upper()):
            flist.append( names)

    return np.sort(flist)


def create_dir(path):
    """ Create a directory. """
    try:
        if not os.path.exists(path):
            os.makedirs(path)
    except OSError:
        print(f"Error: creating directory with name {path}")


if __name__ == "__main__":
    import cv2
    from skimage.measure import label, regionprops
    import pylab as plt
    import glob
    from extract_PolypBoxes import getBBoxCordinatesFromMask_voc 
    
    DIR_LIST = ['flat', 'NBI', 'protuded', 'Neg']
    SUBDIR_LIST = ['C1', 'C2', 'C3', 'C4', 'C5']
    
    BaseFolder = '/Users/sharib/Datasets/PolypGen1.0/EndoCV2021-test_analysis/PolypGen2021_MultiCenterData_v2/'
    
    dataDetailFolder = BaseFolder + 'dataDetails_PolypGen'
    create_dir(dataDetailFolder)
    

    for i in range (0, len(SUBDIR_LIST)):
        centerChoice = i
        
        flatList_DIR = dataDetailFolder +SUBDIR_LIST[centerChoice]+ '-' + DIR_LIST[0]
        protrudedList_DIR = dataDetailFolder + SUBDIR_LIST[centerChoice] + '-' + DIR_LIST[2]
        nbiList_DIR = dataDetailFolder + SUBDIR_LIST[centerChoice] + '-' + DIR_LIST[1]
        neg_DIR = dataDetailFolder  + SUBDIR_LIST[centerChoice] + '-' + DIR_LIST[3]
        
        create_dir(flatList_DIR)
        create_dir(protrudedList_DIR)
        
        create_dir(nbiList_DIR)
        create_dir(neg_DIR)
        
        
        #  Centerwise data
        allImageList = BaseFolder +'data_' + SUBDIR_LIST[centerChoice] + '/images_' + SUBDIR_LIST[centerChoice]
        allMaskList = BaseFolder + 'data_' + SUBDIR_LIST[centerChoice] + '/masks_' + SUBDIR_LIST[centerChoice]
        allboxList = BaseFolder +'data_' + SUBDIR_LIST[centerChoice] + '/bbox_' + SUBDIR_LIST[centerChoice]
        
    
        " Append all images in a list and save bounding boxes"
        
        allfileList = detect_imgs(allImageList, ext='.jpg') 
        allmaskList = detect_imgs(allMaskList, ext='.jpg') 
        
        flatList = detect_imgs_filesOnly(flatList_DIR, ext='_mask.jpg') 
        protrudedList = detect_imgs(protrudedList_DIR, ext='_mask.jpg') 
        nbiList = detect_imgs(nbiList_DIR, ext='_mask.jpg')
    
        
        """ Distinguish below from the data
            1. PolypType: Protruded, flat, none
            2. SizeType: Small, Medium, Large, None
            3. SizeVal: Area 
            4. Num_polyps: no. of polyps per frame
        """
        PolypType = []
        SizeType = []
        annotations_PFrame = []  # sum of sizeNumPFrame
        SizeVal = [] 
        fileName = []
                
        for ii, imageFile in enumerate(allmaskList[:]):
            
            sizeNumPFrame = [0, 0, 0, 0]
            sizeVPFrame = [0, 0, 0, 0] #  taking 4 polyp regions as max available
             
            "listimage files and find the type and modality of polyp"
            fileNameOnly = imageFile.split('/')[-1].split('.')[0]
            image = cv2.imread(allfileList[ii])
            fileName.append(allfileList[ii].split('/')[-1])
    
            
            "distinguish sizes of polyps and quantify numbers for each case"
            gt_mask_files = (cv2.imread(imageFile, 0) > 0).astype(np.uint8)
    
            label_image = label((gt_mask_files>0.8).astype(np.uint8))
            properties = regionprops(label_image)
            a = [prop.area for prop in properties]
            i = 0
            for j in range (0, len( [prop.area for prop in properties])):
                # small
                if (a[j] > 100 and a[j] <= 10000):
                    i = 1
                    sizeNumPFrame[i] = sizeNumPFrame[i]+1
                    sizeVPFrame[i] = a[j]
                # medium
                elif (a[j] > 10000 and a[j] <= 40000):
                    i = 2
                    sizeNumPFrame[i] = sizeNumPFrame[i]+1
                    sizeVPFrame[i] = a[j]
                # large
                elif (a[j] > 40000):
                    print('value of a{}'.format(a[j]))
                    i = 3
                    sizeNumPFrame[i] = sizeNumPFrame[i]+1
                    sizeVPFrame[i] = a[j]
                elif np.sum(gt_mask_files)==0:
                    i = 0
                    sizeNumPFrame[i] = sizeNumPFrame[i]+1
                    sizeVPFrame[i] = a[j]
                
            SizeType.append(sizeNumPFrame)
            SizeVal.append(sizeVPFrame)
            
            annotations_PFrame.append(np.sum(sizeNumPFrame))
                        
    
        
            "check if the file is present in the flat folder if not assign protruded class and assign none if area = 0 below"
            """
            Comparing array to array match: all(tag in fileNameOnly for tag in flatList)):
            """
            
            if (any(fileNameOnly+'.jpg' == flatList)):
                print("flat ")
                PolypType.append('flat')
            elif(np.sum(gt_mask_files)==0):
                print("none")
                PolypType.append('none')
            else:
                print("protruded")
                PolypType.append('protruded')
          
        
        # depending on length try different is      
        print('Total labels for segmentation is:', np.sum(annotations_PFrame))  
        
        "Save in the dataTable format to csv 'polypType': PolypType, "
        import pandas as pd
        data_tab = pd.DataFrame({'fileList': allfileList, 'sizeType': SizeType , 'sizeVal': SizeVal, 'annotations': annotations_PFrame})
        data_tab.to_csv(os.path.join(dataDetailFolder, 'dataDetails_' + SUBDIR_LIST[centerChoice]+'.csv'), index = None)
        
