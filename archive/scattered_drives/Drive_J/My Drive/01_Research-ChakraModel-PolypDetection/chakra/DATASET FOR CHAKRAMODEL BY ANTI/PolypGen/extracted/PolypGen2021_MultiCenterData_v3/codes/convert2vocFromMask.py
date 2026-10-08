#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb  4 11:12:48 2021

@author: sharib
"""
# ls -l -d /home/user012/Desktop/folder2Start/*/
import numpy as np 
import os
    

def detect_imgs(infolder, ext='.tif'):

    items = os.listdir(infolder)
    
    flist = []
    for names in items:
        if names.endswith(ext) or names.endswith(ext.upper()):
            flist.append(os.path.join(infolder, names))

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
    from extract_PolypBoxes import getBBoxCordinatesFromMask_voc 
    import json
    'single frame data folders'
    SUBDIR_LIST_center = ['C5', 'C2', 'C3', 'C4', 'C5']
    
    'Sequence data folder centerwise'
    SUBDIR_LIST = ['data_C2']
    BaseFolder = '/Users/sharib/Datasets/PolypGen1.0/EndoCV2021-test_analysis/PolypGen2021_MultiCenterData_v2/'
    
    # put all bounding boxes into a json file
    # for i in range (0, len(SUBDIR_LIST)):
    #     centerChoice = i
    # for i in range (0, len(SUBDIR_LIST)):
    centerChoice = 1
    
    #  all data (centerwise)
    allImageList = BaseFolder + SUBDIR_LIST[0] + '/' + 'images_' + SUBDIR_LIST_center[centerChoice] 
    allMaskList = BaseFolder + SUBDIR_LIST[0] + '/'  + 'masks_' + SUBDIR_LIST_center[centerChoice] 
    
    bbox_C = BaseFolder  +  SUBDIR_LIST[0] + '/'  + 'bbox_' + SUBDIR_LIST_center[centerChoice] 
    bbox_image = BaseFolder  +  SUBDIR_LIST[0] + '/'  + 'bbox_image_' + SUBDIR_LIST_center[centerChoice] 
    create_dir(bbox_C)
    create_dir(bbox_image)
    
    " Append all images in a list and save bounding boxes"
    
    allfileList = detect_imgs(allImageList, ext='.jpg') 
    allmaskList = detect_imgs(allMaskList, ext='.jpg') 

    for ii, imageFile in enumerate(allfileList[:]):
        "listimage files and find the type and modality of polyp"
        fileNameOnly = imageFile.split('/')[-1].split('.')[0]
        image = cv2.imread(imageFile)
        
        maskFile = allMaskList+'/'+ fileNameOnly+'_mask.jpg'


        bbox_file = os.path.join(bbox_C, fileNameOnly +'.txt')
        imageFileName = os.path.join(bbox_image, fileNameOnly +'_bbox.jpg')
        
        "distinguish sizes of polyps and quantify numbers for each case"
        gt_mask_files = (cv2.imread(maskFile, 0) > 0).astype(np.uint8)

        # convert and write bbox and image with bbox
        image, lines = getBBoxCordinatesFromMask_voc(image, gt_mask_files, bbox_file, 'polyp', 1)
        
        cv2.imwrite(imageFileName, image)
        
        
            

            # fileObj= open(jsonFileName, "a")
            # fileObj.write("\n")
            # json.dump(my_dictionary, fileObj)
            # fileObj.close()