import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np
from skimage.data import imread
from skimage import io
from skimage.color import rgb2gray
from skimage.filter import sobel
from skimage.measure import find_contours, LineModel
from scipy.spatial import distance
from scipy import stats
from sklearn.cluster import DBSCAN
from itertools import cycle
from collections import defaultdict
from pylab import *
from PIL import Image
import math
import os
import sys
import pandas as pd
from skimage.morphology import reconstruction, binary_erosion, rectangle
from skimage.exposure import rescale_intensity

## CONSTANTS ##
CONTOUR_MINLENGTH = 200

def get_mask_from_boundingbox(img, box):
    """
    Given a box (minx,miny,maxx,maxy) and an image, returns a mask for that bounding box
    """
    mask = np.zeros(img.shape,dtype=np.int)
    mask[box[1]:box[3],box[0]:box[2]] = np.int(1)
    return mask > 0.9

def get_center(pointlist):
    """
    Takes in a list of tuples (x,y) and returns the average coordinate
    """
    return np.mean(pointlist, axis=0)

def compute_contours(img, length=300):
    """
    Given an Image object, finds the contours. Filters
    the contours by how long they are (this is the optional length
    argument)

    Returns:
    ret_contours (list of contours),
    ret_lengths (list of lengths of each contour in ret_contours)
    """
    length = CONTOUR_MINLENGTH
    contours = find_contours(img, 0.1)
    contour_lengths = [len(x[:, 1]) for x in contours]
    ret_contours = []
    ret_lengths = []
    for contour in contours:
        if (contour.shape[0] >= length):
            ret_contours.append(contour)
            ret_lengths.append(contour.shape[0])
    return ret_contours, ret_lengths

def process(filename, plot=False):
    # read in image filename
    imagepath = os.path.join(os.getcwd(), filename)
    orig_img = io.imread(filename,True,'pil')
    # binarize image
    img = orig_img > 0.9 # binary threshold
    # convert to grayscale (easier for viewing)
    img = rgb2gray(img)
    imshow(img)
    # use erosion to expland black areas in the document. This will
    # group together small text and make it easier to find contours
    # of signatures, which are usually separated from text
    eroded_img = binary_erosion(img,rectangle(30,10))
    # get contours of eroded image
    contours, lengths = compute_contours(eroded_img)
    # compute X and Y gradients over the contours. We expect that signatures
    # will have have a constant gradient that is close to the length of
    # the contour. We take the sum of the X-gradient to remove contours
    # that are vertically biased
    c_grad_x = map(lambda x: np.gradient(x[:,1]), contours)
    c_grad_y = map(lambda x: np.gradient(x[:,0]), contours)
    stuffs = []
    for i,(x,y) in enumerate(zip(c_grad_x,c_grad_y)):
        stuffs.append( (sum(map(abs, x)), len(x)) )
    d = pd.DataFrame.from_records(stuffs)
    d['diff'] = abs(d[0] - d[1])
    d = d[d['diff'] > d['diff'].mean()]
    contours = [contours[i] for i in d.index]
    # compute bounding boxes for resulting contours
    boxes = get_boundingboxes(contours)
    # given a box, does sobel on the bounding box of that block
    # computes contours within the subimage and returns them
    def process_block(box):
        mask = get_mask_from_boundingbox(img,box)
        sobel_img = sobel(img,mask)
        contours, lengths = compute_contours(sobel_img)
        return len(contours),contours,lengths
    # get all blocks
    blocks = [process_block(box) for box in boxes]
    # retrieve the blocks that have the fewest number of contours
    num_contours = pd.Series(block[0] for block in blocks)
    num_contours = num_contours[num_contours < num_contours.mean()]
    # plot only those contours
    ret_contours = []
    for block in [blocks[i] for i in num_contours.index]:
        len_con,contours,lengths = block
        lengths = pd.Series(lengths)
        lengths = lengths[lengths > lengths.mean()]
        for i in lengths.index:
            contour = contours[i]
            ret_contours.append(contour)
            plt.plot(contour[:,1],contour[:,0])
    return ret_contours

def get_boundingboxes(contours, plot=False):
    """
    Given a list of contours, computes the bounding box
    for each and returns the list
    """
    boxes = []
    for contour in contours:
        # compute bounding box coordinates
        minx = miny = float('inf')
        maxx = maxy = float('-inf')
        minx = min(minx, min(contour, key=lambda x: x[1])[1])
        miny = min(miny, min(contour, key=lambda x: x[0])[0])
        maxx = max(maxx, max(contour, key=lambda x: x[1])[1])
        maxy = max(maxy, max(contour, key=lambda x: x[0])[0])
        if plot:
            x = (minx, maxx, maxx, minx, minx)
            y = (miny, miny, maxy, maxy, miny)
            plt.plot(x,y,'-b',linewidth=2)
        boxes.append( map(int,(minx,miny,maxx,maxy)) )
    return boxes

def get_subimage(imgpath, box, filename):
    """
    Takes as argument a box given by [minx, miny, maxx, maxy], an image
    and a filename. Crops the image and saves the result to filename
    """
    img = Image.open(imgpath)
    box = map(int, box)
    img.crop(box).save(filename)


if __name__ == '__main__':
    plt.gray()
    imagepath = sys.argv[1]
    f=plt.figure(figsize=(16,12))
    basename = ''.join(imagepath.split('/')[-1].split('.')[:-1])
    contours = process(imagepath,plot=False)
    get_boundingboxes(contours,plot=False)
    plt.savefig(basename+'-signature.png')
