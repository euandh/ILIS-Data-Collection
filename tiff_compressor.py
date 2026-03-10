# -*- coding: utf-8 -*-
"""
Created on Thu Mar  5 11:53:27 2026

Compress-a-tron 5000

Compress those massive tiff files down to a hdf5

@author: edh1g18
"""

import tifffile
import h5py

def tiff_to_h5(input_fp, output_fp):
    print(f"Opening {input_fp}")
    with tifffile.TiffFile(input_fp) as tiff_in:
        num_frames = len(tiff_in.pages)
        
        frame_0 = tiff_in.pages[0].asarray()
        h,w = frame_0.shape
        data_type = frame_0.dtype
        
        print(f"File has {num_frames} frames, each {w}x{h} px./nCompressing now to HDF5 at {output_fp}")
        
        with h5py.File(output_fp, 'w') as h5_out:
            dataset = h5_out.create_dataset(
                'espray',
                shape = (num_frames, h, w),
                dtype = data_type,
                compression = 'gzip',
                compression_opts=9)
            
            for i, page in enumerate(tiff_in.pages):
                dataset[i] = page.asarray()
                
                if i % 10 == 0:
                    print(f"Converted frame {i}/{num_frames}")
                
                
    print("Conversion complete.")
                
input_fp = "C:/Users/edh1g18/localfiles/test files/ESPRAY_2026-03-10_1546_IMAGES.tiff"
output_fp ="C:/Users/edh1g18/localfiles/test files/ESPRAY_2026-03-10_1546_IMAGES_COMPRESSED.h5"
tiff_to_h5(input_fp, output_fp)