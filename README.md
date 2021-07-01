# radiomics-tools
Python snippets that for doing radiomics analysis on medical images.  Operations include the following:
* Read/write DICOM and NIfTI files (using pydicom[[1]](#1) and NiBabel[[2]](#2))
* Rasterize ImageJ[[2]](#2) contours (using read_roi[[3]](#3))
* Generate .CSV files of radiomics statistics from NIfTI images and masks (using pyradiomics[[4]](#4))

**Emphatic Caveat (!)**:
No attempt has been made to exhaustively test these tools on a sample of different variations of images and ROIs from different sources.  These are just tools that *I* have developed for my own use on radiomics projects.  These scripts are posted on GitHub not for distribution, but rather just for research transparency and accountability.  But please help yourself, if there's anything in here that you find useful.

### imagej_rois_to_nifti


## References
<a id="1">[1]</a> 
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.4295521.svg)](https://doi.org/10.5281/zenodo.4295521)

<a id="2">[2]</a> 
Schneider, C. A., Rasband, W. S., & Eliceiri, K. W. (2012). NIH Image to ImageJ: 25 years of image analysis. Nature Methods, 9(7), 671–675. doi:10.1038/nmeth.2089

<a id="3">[3]</a> 
https://github.com/hadim/read-roi

<a id="4">[4]</a> 
van Griethuysen, J. J. M., Fedorov, A., Parmar, C., Hosny, A., Aucoin, N., Narayan, V., Beets-Tan, R. G. H., Fillon-Robin, J. C., Pieper, S., Aerts, H. J. W. L. (2017). Computational Radiomics System to Decode the Radiographic Phenotype. Cancer Research, 77(21), e104–e107. `https://doi.org/10.1158/0008-5472.CAN-17-0339 <https://doi.org/10.1158/0008-5472.CAN-17-0339>
