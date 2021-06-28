#!/usr/bin/env python3
"""
---===[ imagej_rois_to_nifti: radiomics-tools ]===---
 Created on June 27, 2021
 Copyright 2021 - Nick D. James

Rasterizes a sequence of ImageJ-drawn contours for a stack of 2D DICOM images.  The corresponding stack of 2D masks
is saved as a NIfTI1 .nii.gz file.  The rasterization is done according to the given directory of images.  One mask
(of matching dimensions) is created for each image.  A "blank" mask is created for images lacking a corresponding roi
in the .zip file.  The default background value for masks is configurable (default: 0).

Four Parameters:
    * Path to directory containing the DICOM images
    * Path to a .zip file of ImageJ contours that match the images
    * Path to the output directory into which the .nii.gz file will be written (under the same name as its .zip file)
    * Value for the "region of boredom" (pixel values outside the regions of interest) -- default: 0
"""
import sys
import os
import logging
import numpy as np
import pydicom
from pydicom import errors
from inspect import signature
from read_roi import read_roi_zip
from zipfile import BadZipFile
import skimage.draw
import nibabel as nib
import subprocess


def get_parent_dir_of_this_file():
    return os.path.split(os.path.realpath(__file__))[0]


def refresh_requirements_txt():
    """Executes `pip freeze > 'requirements.txt'`.  Use this to automate the version control of the virtualenv.
    """
    reqs = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'])
    filename = os.path.join(get_parent_dir_of_this_file(), 'requirements.txt')
    with open(filename, 'w') as f:
        f.write(reqs.decode())


def sort_names_numerically(filename_list):
    """Named after the checkbox in ImageJ's "Import --> Image Sequence" dialog box Sorts the given filename list the
    same way ImageJ does if that checkbox is checked (and if the file is either not DICOM or the (0020, 0018) Instance
    Number tag is blank): hierarchically, by sequence component (e.g. 7.55.8 < 7.123.2) rather than lexicographically
    (individual string components are, however, sorted lexicographically).
    :param filename_list: List of filenames that are .-delimited strings or numbrers with a .dcm extension.
    """
    def int_or_str(s):
        try:
            return int(s)
        except ValueError:
            return s
    filename_list.sort(key=lambda filename: [int_or_str(x) for x in filename.split('.')[:-1]])


def get_dcm_file_seq(input_dir):
    """Returns the list of DICOM filenames in input_dir, sorted in their sequence order.
    Determining sequence order in a completely general, robust way can actually get surprisingly tricky.  Here,
    we're using a somewhat oversimplified approach (but it usually works...I think):
    - If the (0020, 0018) Instance Number tag exists and is unique in all the DICOM files, we sort by those in
      increasing order.
    - Otherwise, sort according to ImageJ's "sort names numerically" feature.
    :param input_dir: Directory containing a sequence of DICOM images.
    :return: List of DICOM filenames in input_dir, sorted in their sequence order.
    """
    # Make a list of (filename, DICOM header)-pairs for all the DICOM files in input_dir
    headers = []
    for filename in os.listdir(input_dir):
        try:
            dcm = pydicom.dcmread(os.path.join(input_dir, filename), stop_before_pixels=True)
        
        # If filename is not a DICOM file, move on to the next one; otherwise add it to the list
        except pydicom.errors.InvalidDicomError:
            continue
        headers.append((filename, dcm))
    
    # If the Instance Number fields exist and are all unique, sort by those
    try:
        # Get the list of instance numbers from each header
        inst_num_values = [x[1].InstanceNumber for x in headers]
        
        # If they're all unique...
        if len(set(inst_num_values)) == len(inst_num_values):
            
            # Sort the list of (filename, header)-pairs by instance number
            headers.sort(key=lambda x: x[1].InstanceNumber)
            
            # And return just the filenames (keeping the sort order)
            return [x[0] for x in headers]
        else:
            logging.warning("Duplicate instance numbers in %s", input_dir)
    
    # If something went wrong just trying to LOOK at the Instance Numbers, log it.
    except NotImplementedError:
        logging.error("Corrupt/missing instance numbers in %s", input_dir)
    
    # If we can't sort by Instance Number, fall back on ImageJ's filename-based, header-independent sort
    filename_list = [x[0] for x in headers]
    sort_names_numerically(filename_list)
    return filename_list


def roi_to_mask(roi_record, img, region_of_boredom_value=0):
    """Rasterizes an ImageJ ROI record into a 2D numpy array containing 1s inside the ROI and a different value
    outside it.
    :param roi_record: ROI record from a .roi or .zip file
    :param img: a numpy image array of the size and type wanted for the mask.
    :param region_of_boredom_value: The filler value used for the background outside the ROI.
    :return:
    """
    mask = region_of_boredom_value * np.ones_like(img)
    roi_record_type = roi_record['type']
    if roi_record_type == "freehand":
        
        # Get the x,y-coords of all points inside ROI
        c, r = np.asarray(roi_record['x']), np.asarray(roi_record['y'])
        mask[skimage.draw.polygon(r, c)] = 1
    
    elif roi_record_type == "oval":
        top, left = roi_record['top'], roi_record['left']
        width, height = roi_record['width'], roi_record['height']
        
        # ImageJ puts y=0 at the top of the image
        r_radius, c_radius = height // 2, width // 2
        r, c = top + r_radius, left + c_radius
        mask[skimage.draw.ellipse(r=r, c=c, r_radius=r_radius, c_radius=c_radius)] = 1
    
    # A "composite" contour is a dict with a list of paths (roi_record['paths']).
    # Each path is a list of (x,y) pairs.
    # 'top', 'left', 'width', 'height' are keys for the dimensions of the bounding box containing all paths.
    elif roi_record_type == 'composite':
        for p in roi_record['paths']:
            p = np.asarray(p)
            c, r = np.asarray(p)[:, 0], np.asarray(p)[:, 1]
            mask[skimage.draw.polygon(r, c)] = 1
    else:
        logging.error("Unrecognized ROI record type: \"%s\"",
                      roi_record['name'], roi_record_type, roi_record_type)
    return mask


def rois_to_mask_stack(roi_odict, input_dir, dcm_list):
    """Creates numpy array mask from an ImageJ ROI and loads the corresponding DICOM image into another np array.
    :param roi_odict: The contents of an RoiSet zip file produced by read_roi_zip
    :param input_dir: Directory containing the DICOM files for this RoiSet zip file
    :param dcm_list: List of DICOM filenames
    """
    # Load the first image in `dcm_list` to see what the mask dimensions should be.  (Note: we're assuming all images
    # in the list are the same size)
    input_filename = os.path.join(input_dir, dcm_list[0])
    try:
        dicom_record = pydicom.dcmread(input_filename)
        img = dicom_record.pixel_array.astype(float)
    except TypeError:
        logging.error("Could not access Pixel Data in %s", input_filename)
        return
    
    # Create H x W x D array of zeros to hold masks
    mask_shape = tuple(list(img.shape) + [len(dcm_list)])
    mask = np.zeros(mask_shape)
    
    # Convert each ROI record to a slice in the 3D mask
    for roi_record in roi_odict.values():
        # The 'position' field in the ROI record contains the index of the corresponding .dcm file
        i = int(roi_record['position']) - 1
        
        # Rasterize the ROI and record it at position i
        mask[:, :, i] = roi_to_mask(roi_record, img)
    return mask


def get_dicom_roi_seqs(input_dir, roi_set_zip_file):
    """Gets an iterator of ROIs from a .zip file and the list of all DICOM images in the corresponding directory.
    :param input_dir: path containing the DICOM images
    :param roi_set_zip_file: path to the RoiSet.zip file containing the regions of interest
    :returns: iterator of ROIs, list of DICOM files
    """
    # Read the ROI zip file sitting in the input dir
    roi_odict = None
    try:
        roi_odict = read_roi_zip(roi_set_zip_file)
    except (BadZipFile, UnboundLocalError):
        logging.error("Skip dir (bad RoiSet.zip file): " + roi_set_zip_file)
    
    # Get the list of DICOM filenames of this sequence in their proper order
    dcm_seq = get_dcm_file_seq(input_dir)
    
    # If there aren't any DICOMs, that's messed up.  Please make a note of it.
    if dcm_seq:
        logging.info("%d dicom images in %s", len(dcm_seq), input_dir)
    else:
        logging.error("RoiSet.zip file with no DICOM files in %s", input_dir)
    return roi_odict, dcm_seq


def mask_arr_to_nifti1_file(mask_arr, zip_file, output_path):
    """Writes mask array to NIfTI file.
    :param mask_arr: 3D numpy array of floats (3rd axis is slice number)
    :param zip_file: path to ImageJ ROI .zip file
    :param output_path: path to output nifti file
    """
    nifti_img = nib.Nifti1Image(mask_arr, affine=np.eye(4))
    output_file = os.path.join(output_path, os.path.split(os.path.splitext(zip_file)[0])[1]) + ".nii.gz"
    nib.save(nifti_img, output_file)


def main(dicom_dir, roi_zip_path, output_dir):
    """See file header for description.
    :param dicom_dir: Directory of DICOM images
    :param roi_zip_path: Path to .zip file of ImageJ contours
    :param output_dir: Directory in which to put the NIfTI mask file
    """
    # Set up the logging module
    log_filename = __file__ + ".log"
    logging.basicConfig(filename=log_filename, format="%(levelname)s: %(message)s", level=logging.WARNING)

    # Get the ordered dictionary of ROIs and the list of DICOM files
    ordd_dict, dcm_seq = get_dicom_roi_seqs(dicom_dir, roi_zip_path)
    
    # Create the X x Y x Z numpy array of masks
    mask_arr = rois_to_mask_stack(ordd_dict, dicom_dir, dcm_seq)
    
    # Write NIfTI file
    mask_arr_to_nifti1_file(mask_arr, roi_zip_path, output_dir)


def usage():
    print("Usage: imagej_rois_to_nifti " + " ".join(signature(main).parameters))


if __name__ == "__main__":
    refresh_requirements_txt()
    if len(sys.argv) - 1 != len(signature(main).parameters):
        usage()
    else:
        main(*sys.argv[1:])
