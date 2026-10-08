#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb  3 20:29:04 2021

@author: sharib
"""

"Extract boxes"

import cv2
import numpy as np
import skimage.draw

categoryList = ['polyp']

class_rgb = [
    (0, 0, 255), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 255, 255),
    (255, 0, 255), (192, 192, 192), (128, 128, 128), (128, 0, 0),
    (128, 128, 0), (0, 128, 0), (128, 0, 128), (0, 128, 128), (0, 0, 128)]


def mask_splitting(label_image):
    uniq, cnts = np.unique(label_image, return_counts=True)
    cnts = cnts[np.where(cnts > 100)]
    uniq = uniq[np.where(cnts > 100)]
    # zero is background
    if len(cnts) <=2:
        list_seg = list(zip(uniq, cnts))[1:]
        largest = max(list_seg, key=lambda x:x[1])[0]
        labels_max = (label_image==largest).astype(int)
        maskCordinates=cv2.findNonZero(labels_max)
        
    else:
        list_seg = list(zip(uniq, cnts))[1:]
        for i in range(0, len(list_seg)-1):
            largest = max([list_seg[i-1]], key=lambda x:x[1])[0]
            labels_max = (label_image==largest).astype(int)
            maskCordinates=cv2.findNonZero(labels_max)
    return maskCordinates

            
def draw_line(img, x, y, height, width, color):
    cv2.line(img, (x, 0), (x, height), color, thickness=2)
    cv2.line(img, (0, y), (width, y), color, thickness=2)
    return img

# writing bbox
def save_bb(txt_path, line):
    with open(txt_path, 'a') as myfile:
        myfile.write(line + "\n") # append line
        
def voc_format(class_index, coord):
    # Order: xmin ymin xmax ymax class
    # Top left pixel is (1, 1) in VOC
    xmin = np.min(coord[:,0,0])+1
    ymin = np.min(coord[:,0,1])+1
    xmax = np.max(coord[:,0,0])+1
    ymax = np.max(coord[:,0,1])+1
    items = map(str, [class_index, xmin, ymin, xmax, ymax ])
    return ' '.join(items)

def voc_format_v2(class_index, xmin, ymin, xmax, ymax):
    items = map(str, [class_index, xmin, ymin, xmax, ymax ])
    return ' '.join(items)



def valRect(coord):
    xmin = np.min(coord[:,0,0])+1
    ymin = np.min(coord[:,0,1])+1
    xmax = np.max(coord[:,0,0])+1
    ymax = np.max(coord[:,0,1])+1
    return [xmin, ymin, xmax, ymax]

def getBBoxCordinatesFromMask_voc(image, im_mask, txt_path, classCategory, ll, debug=0):
    from skimage.measure import label, regionprops
    # maskCordinates=cv2.findNonZero(im_mask)
    
    label_image = label((im_mask>0.8).astype(np.uint8))
    properties = regionprops(label_image)
    xminList = []  
    line = []
    
    for props in properties:
        
        if props.area > 100:
            print('Found bbox', props.bbox)
            print('Found area', props.area)
            cv2.rectangle(image, (props.bbox[1], props.bbox[0]), (props.bbox[3], props.bbox[2]), (255, 0, 0), 2 )
    
            xmin, ymin, xmax, ymax = props.bbox[1], props.bbox[0], props.bbox[3], props.bbox[2]
           
            
            if all(x !=xmin for x in xminList):  
                xminList.append(xmin)
                line = voc_format_v2(classCategory, xmin, ymin, xmax, ymax)
                # line = voc_format(classCategory, maskCordinates)
                save_bb(txt_path, line)
    if line == []:
        save_bb(txt_path, '') 
    # color = class_rgb[ll]
    # img=cv2.rectangle(image, (xmin, ymin), (xmax, ymax), color, 2)
    return image, line

# write to the yolo format
def yolo_format(class_index, coord, width, height):
    [xmin, ymin, xmax, ymax] = valRect(coord)
    x_center = (xmin + xmax) / float(2.0 * width)
    y_center = (ymin + ymax) / float(2.0 * height)
    x_width = float(abs(xmax - xmin)) / width
    y_height = float(abs(ymax - ymin)) / height
    return str(class_index) + " " + str(x_center) \
       + " " + str(y_center) + " " + str(x_width) + " " + str(y_height)

def getBBoxCordinatesFromMask_yolo(image, im_mask, txt_path, classCategory, ll, width, height): 
    maskCordinates=cv2.findNonZero(im_mask)
    k = ll
    line=yolo_format(k, maskCordinates, width, height)
    save_bb(txt_path, line)
    [xmin, ymin, xmax, ymax] = valRect(maskCordinates)
    color = class_rgb[ll]
    img=cv2.rectangle(image, (xmin, ymin), (xmax, ymax), color, 2)
    return img