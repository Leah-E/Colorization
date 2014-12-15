import numpy as np
import matplotlib.pyplot as plt
from scipy import misc
from scipy import io
from scipy import sparse
from scipy.sparse import linalg
import colorsys
import os
import time
import sys

os.system('cls')
os.system('reset')

def yiq_to_rgb(y, i, q):                                                        # the code from colorsys.yiq_to_rgb is modified to work for arrays
    r = y + 0.948262*i + 0.624013*q
    g = y - 0.276066*i - 0.639810*q
    b = y - 1.105450*i + 1.729860*q
    r[r < 0] = 0
    r[r > 1] = 1
    g[g < 0] = 0
    g[g > 1] = 1
    b[b < 0] = 0
    b[b > 1] = 1
    return (r, g, b)

# ---------------------------------------------------------------------------- #
# ------------------------------- PREPARE ------------------------------------ #
# ---------------------------------------------------------------------------- #

dir_path = os.path.dirname(os.path.realpath(__file__))
original = misc.imread(os.path.join(dir_path, 'example.bmp'))
marked = misc.imread(os.path.join(dir_path, 'example_marked.bmp'))

original = original.astype(float)/255
marked = marked.astype(float)/255

isColored = abs(original - marked).sum(2) > 0.01                                # isColored as colorIm 

(Y,_,_) = colorsys.rgb_to_yiq(original[:,:,0],original[:,:,1],original[:,:,2])
(_,I,Q) = colorsys.rgb_to_yiq(marked[:,:,0],marked[:,:,1],marked[:,:,2])

YUV = np.zeros(original.shape)                                                  # YUV as ntscIm
YUV[:,:,0] = Y
YUV[:,:,1] = I
YUV[:,:,2] = Q

'''
max_d = np.floor(np.log(min(YUV.shape[0],YUV.shape[1]))/np.log(2)-2)
iu = np.floor(YUV.shape[0]/(2**(max_d - 1))) * (2**(max_d - 1))
ju = np.floor(YUV.shape[1]/(2**(max_d - 1))) * (2**(max_d - 1))
colorIm = colorIm[:iu,:ju]
YUV = YUV[:iu,:ju]
'''
                                                                                # ALTERNATIVE :: colorized = abs(getColorExact( colorIm, YUV ));

# ---------------------------------------------------------------------------- #
# ---------------------------- getExactColor --------------------------------- #
# ---------------------------------------------------------------------------- #

                                                                                # YUV as ntscIm
n = YUV.shape[0]                                                                # n = image height
m = YUV.shape[1]                                                                # m = image width
image_size = n*m

indices_matrix = np.arange(image_size).reshape(n,m,order='F').copy()            # indices_matrix as indsM

wd = 1                                                                          # The radius of window around the pixel to assess
nr = (2*wd + 1)**2                                                              # The number of pixels in the window
max_nr = image_size * nr                                                        # Maximal size of pixels to assess for the hole image
                                                                                # (for now include the full window also for the border pixels)
row_inds = np.zeros((max_nr, 1), dtype=np.int64)
col_inds = np.zeros((max_nr, 1), dtype=np.int64)
vals = np.zeros((max_nr, 1))

# ----------------------------- Interation ----------------------------------- #

length = 0
pixel_nr = 0                                                                    # the nr of the current pixel, this corresponds to the row index in sparse matrix

for j in range(m):                                                             # iterate over pixels in the image
    for i in range(n):
        
        if (not isColored[i,j]):                                               # The pixel is not colored yet            
            window_index = 0                                                    # tlen as window_index
            window_vals = np.zeros(nr)                                          # window_vals as gvals 
                                                                                # iterate over pixels in the window with the center [i,j]
            for ii in range(max(0, i-wd), min(i+wd+1,n)):
                for jj in range(max(0, j-wd), min(j+wd+1, m)):
                    if (ii != i or jj != j):                                    # not the center pixel
                        row_inds[length,0] = pixel_nr
                        col_inds[length,0] = indices_matrix[ii,jj]
                        window_vals[window_index] = YUV[ii,jj,0]
                        length += 1
                        window_index += 1
            
            center = YUV[i,j,0].copy()                                          # t_val as center
            window_vals[window_index] = center
            
                                                                                # calculate variance of the intensities in a window around pixel [i,j]
            variance = np.mean((window_vals[0:window_index+1] - np.mean(window_vals[0:window_index+1]))**2) # # c_var as variance            
            sigma = variance * 0.6                                              #csig as sigma
            
            mgv = min(( window_vals[0:window_index+1] - center )**2)            
            if (sigma < ( -mgv / np.log(0.01 ))):
                sigma = -mgv / np.log(0.01)                                     
            if (sigma < 0.000002):                                              # avoid dividing by 0
                sigma = 0.000002
            
            window_vals[0:window_index] = np.exp( -((window_vals[0:window_index] - center)**2) / sigma )    # use weighting funtion (2)
            window_vals[0:window_index] = window_vals[0:window_index] / np.sum(window_vals[0:window_index]) # make the weighting function sum up to 1
            vals[length-window_index:length,0] = -window_vals[0:window_index]
        
        # END IF
        
                                                                                # add the values for the current pixel
        row_inds[length,0] = pixel_nr
        col_inds[length,0] = indices_matrix[i,j]
        vals[length,0] = 1
        length += 1
        pixel_nr += 1
        
    # END OF FOR i
# END OF FOR j

# ---------------------------------------------------------------------------- #
# ------------------------ After Iteration Process --------------------------- #
# ---------------------------------------------------------------------------- #
                                                                                # trim to variables to the actually used length that does not include the full window for the border pixels
vals = vals[0:length,0]
col_inds = col_inds[0:length,0]
row_inds = row_inds[0:length,0]

# ------------------------------- Sparseness --------------------------------- #

A = sparse.csr_matrix((vals, (row_inds, col_inds)), (pixel_nr, image_size))
io.mmwrite(os.path.join(dir_path, 'sparse_matrix'), A)

colorized = np.zeros(YUV.shape)                                                 # colorized as nI = resultant colored image
colorized[:,:,0] = YUV[:,:,0]

color_copy_for_nonzero = isColored.reshape(image_size).copy()                   # We have to reshape and make a copy of the view of an array for the nonzero() to work like in MATLAB
colored_inds = np.nonzero(color_copy_for_nonzero)                               # colored_inds as lblInds

b = np.zeros((A.shape[0], 1))
for t in [1,2]:
    curIm = YUV[:,:,t].reshape(A.shape[0], 1)
    b[colored_inds] = curIm[colored_inds]
    new_vals = linalg.spsolve(A, b)                                             # new_vals = linalg.lsqr(A, b)[0] # least-squares solution (much slower), different solutions
    colorized[:,:,t] = new_vals.reshape(n, m, order='F').copy()
    
# ---------------------------------------------------------------------------- #
# ------------------------------- CONCLUDE ----------------------------------- #
# ---------------------------------------------------------------------------- #

(R, G, B) = yiq_to_rgb(colorized[:,:,0],colorized[:,:,1],colorized[:,:,2])
colorizedRGB = np.zeros(original.shape)
colorizedRGB[:,:,0] = R                                                         # colorizedRGB as colorizedIm
colorizedRGB[:,:,1] = G
colorizedRGB[:,:,2] = B

plt.imshow(colorizedRGB)
plt.show()

misc.imsave(os.path.join(dir_path, 'example_colorized.bmp'), colorizedRGB)
