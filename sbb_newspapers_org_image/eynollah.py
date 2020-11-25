"""
tool to extract table form data from alto xml data
"""

import gc
import math
import os
import random
import sys
import time
import warnings
from multiprocessing import Process, Queue, cpu_count
from sys import getsizeof

import cv2
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
stderr = sys.stderr
sys.stderr = open(os.devnull, "w")
from keras import backend as K
from keras.models import load_model
sys.stderr = stderr
import tensorflow as tf
tf.get_logger().setLevel("ERROR")
warnings.filterwarnings("ignore")

from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d
from shapely import geometry
from lxml import etree as ET
from matplotlib import pyplot, transforms
import matplotlib.patches as mpatches
import imutils

from .utils import (
    boosting_headers_by_longshot_region_segmentation,
    contours_in_same_horizon,
    crop_image_inside_box,
    filter_contours_area_of_image_interiors,
    filter_contours_area_of_image_tables,
    filter_small_drop_capitals_from_no_patch_layout,
    find_contours_mean_y_diff,
    find_features_of_contours,
    find_features_of_lines,
    find_new_features_of_contoures,
    find_num_col,
    find_num_col_by_vertical_lines,
    find_num_col_deskew,
    find_num_col_only_image,
    get_text_region_boxes_by_given_contours,
    get_textregion_contours_in_org_image,
    isNaN,
    otsu_copy,
    otsu_copy_binary,
    resize_image,
    return_bonding_box_of_contours,
    return_contours_of_image,
    return_contours_of_interested_region,
    return_contours_of_interested_region_and_bounding_box,
    return_contours_of_interested_region_by_min_size,
    return_contours_of_interested_textline,
    return_hor_spliter_by_index_for_without_verticals,
    return_parent_contours,
    rotate_image,
    rotate_max_area,
    rotate_max_area_new,
    rotatedRectWithMaxArea,
    rotation_image_new,
    rotation_not_90_func,
    rotation_not_90_func_full_layout,
    seperate_lines,
    seperate_lines_new_inside_teils,
    seperate_lines_new_inside_teils2,
    seperate_lines_vertical_cont,
    delete_seperator_around,
    return_regions_without_seperators,
    return_deskew_slop,
    put_drop_out_from_only_drop_model,
    putt_bb_of_drop_capitals_of_model_in_patches_in_layout,
    check_any_text_region_in_model_one_is_main_or_header,
    small_textlines_to_parent_adherence2,
    return_contours_of_interested_region_by_size,
    order_and_id_of_texts,
    order_of_regions,
    implent_law_head_main_not_parallel,
    return_hor_spliter_by_index,
    combine_hor_lines_and_delete_cross_points_and_get_lines_features_back_new,
    return_points_with_boundies,
    textline_contours_postprocessing,
    find_number_of_columns_in_document,
    return_boxes_of_images_by_order_of_reading_new,
)


SLOPE_THRESHOLD = 0.13
VERY_LARGE_NUMBER = 1000000000000000000000


class eynollah:
    def __init__(
        self,
        image_dir,
        f_name,
        dir_out,
        dir_models,
        dir_of_cropped_images=None,
        dir_of_layout=None,
        dir_of_deskewed=None,
        dir_of_all=None,
        allow_enhancement=False,
        curved_line=False,
        full_layout=False,
        allow_scaling=False,
        headers_off=False
    ):
        self.image_dir = image_dir  # XXX This does not seem to be a directory as the name suggests, but a file
        self.dir_out = dir_out
        self.f_name = f_name
        self.dir_of_cropped_images = dir_of_cropped_images
        self.allow_enhancement = allow_enhancement
        self.curved_line = curved_line
        self.full_layout = full_layout
        self.allow_scaling = allow_scaling
        self.dir_of_layout = dir_of_layout
        self.headers_off = headers_off
        self.dir_of_deskewed = dir_of_deskewed
        self.dir_of_all = dir_of_all
        if self.f_name is None:
            try:
                self.f_name = image_dir.split("/")[len(image_dir.split("/")) - 1]
                self.f_name = self.f_name.split(".")[0]
            except:
                self.f_name = self.f_name.split(".")[0]
        self.dir_models = dir_models
        self.kernel = np.ones((5, 5), np.uint8)

        self.model_dir_of_enhancemnet = dir_models + "/model_enhancement.h5"
        self.model_dir_of_col_classifier = dir_models + "/model_scale_classifier.h5"
        self.model_region_dir_p = dir_models + "/model_main_covid19_lr5-5_scale_1_1_great.h5"  # dir_models +'/model_main_covid_19_many_scalin_down_lr5-5_the_best.h5'#'/model_main_covid19_lr5-5_scale_1_1_great.h5'#'/model_main_scale_1_1und_1_2_corona_great.h5'
        # self.model_region_dir_p_ens = dir_models +'/model_ensemble_s.h5'#'/model_main_covid19_lr5-5_scale_1_1_great.h5'#'/model_main_scale_1_1und_1_2_corona_great.h5'
        self.model_region_dir_p2 = dir_models + "/model_main_home_corona3_rot.h5"

        self.model_region_dir_fully_np = dir_models + "/model_no_patches_class0_30eopch.h5"
        self.model_region_dir_fully = dir_models + "/model_3up_new_good_no_augmentation.h5"  # "model_3col_p_soft_10_less_aug_binarization_only.h5"

        self.model_page_dir = dir_models + "/model_page_mixed_best.h5"
        self.model_region_dir_p_ens = dir_models + "/model_ensemble_s.h5"  # dir_models +'/model_main_covid_19_many_scalin_down_lr5-5_the_best.h5' #dir_models +'/model_ensemble_s.h5'
        ###self.model_region_dir_p = dir_models +'/model_layout_newspapers.h5'#'/model_ensemble_s.h5'#'/model_layout_newspapers.h5'#'/model_ensemble_s.h5'#'/model_main_home_5_soft_new.h5'#'/model_home_soft_5_all_data.h5' #'/model_main_office_long_soft.h5'#'/model_20_cat_main.h5'
        self.model_textline_dir = dir_models + "/model_textline_newspapers.h5"  #'/model_hor_ver_home_trextline_very_good.h5'# '/model_hor_ver_1_great.h5'#'/model_curved_office_works_great.h5'

    def predict_enhancement(self, img):
        model_enhancement, session_enhancemnet = self.start_new_session_and_model(self.model_dir_of_enhancemnet)

        img_height_model = model_enhancement.layers[len(model_enhancement.layers) - 1].output_shape[1]
        img_width_model = model_enhancement.layers[len(model_enhancement.layers) - 1].output_shape[2]
        # n_classes = model_enhancement.layers[len(model_enhancement.layers) - 1].output_shape[3]
        if img.shape[0] < img_height_model:
            img = cv2.resize(img, (img.shape[1], img_width_model), interpolation=cv2.INTER_NEAREST)

        if img.shape[1] < img_width_model:
            img = cv2.resize(img, (img_height_model, img.shape[0]), interpolation=cv2.INTER_NEAREST)

        margin = True

        if margin:
            kernel = np.ones((5, 5), np.uint8)

            margin = int(0 * img_width_model)

            width_mid = img_width_model - 2 * margin
            height_mid = img_height_model - 2 * margin

            img = img / float(255.0)

            img_h = img.shape[0]
            img_w = img.shape[1]

            prediction_true = np.zeros((img_h, img_w, 3))
            mask_true = np.zeros((img_h, img_w))
            nxf = img_w / float(width_mid)
            nyf = img_h / float(height_mid)

            if nxf > int(nxf):
                nxf = int(nxf) + 1
            else:
                nxf = int(nxf)

            if nyf > int(nyf):
                nyf = int(nyf) + 1
            else:
                nyf = int(nyf)

            for i in range(nxf):
                for j in range(nyf):

                    if i == 0:
                        index_x_d = i * width_mid
                        index_x_u = index_x_d + img_width_model
                    elif i > 0:
                        index_x_d = i * width_mid
                        index_x_u = index_x_d + img_width_model

                    if j == 0:
                        index_y_d = j * height_mid
                        index_y_u = index_y_d + img_height_model
                    elif j > 0:
                        index_y_d = j * height_mid
                        index_y_u = index_y_d + img_height_model

                    if index_x_u > img_w:
                        index_x_u = img_w
                        index_x_d = img_w - img_width_model
                    if index_y_u > img_h:
                        index_y_u = img_h
                        index_y_d = img_h - img_height_model

                    img_patch = img[index_y_d:index_y_u, index_x_d:index_x_u, :]

                    label_p_pred = model_enhancement.predict(img_patch.reshape(1, img_patch.shape[0], img_patch.shape[1], img_patch.shape[2]))

                    seg = label_p_pred[0, :, :, :]
                    seg = seg * 255

                    if i == 0 and j == 0:
                        seg = seg[0 : seg.shape[0] - margin, 0 : seg.shape[1] - margin]
                        prediction_true[index_y_d + 0 : index_y_u - margin, index_x_d + 0 : index_x_u - margin, :] = seg

                    elif i == nxf - 1 and j == nyf - 1:
                        seg = seg[margin : seg.shape[0] - 0, margin : seg.shape[1] - 0]
                        prediction_true[index_y_d + margin : index_y_u - 0, index_x_d + margin : index_x_u - 0, :] = seg

                    elif i == 0 and j == nyf - 1:
                        seg = seg[margin : seg.shape[0] - 0, 0 : seg.shape[1] - margin]

                        prediction_true[index_y_d + margin : index_y_u - 0, index_x_d + 0 : index_x_u - margin, :] = seg

                    elif i == nxf - 1 and j == 0:
                        seg = seg[0 : seg.shape[0] - margin, margin : seg.shape[1] - 0]

                        prediction_true[index_y_d + 0 : index_y_u - margin, index_x_d + margin : index_x_u - 0, :] = seg

                    elif i == 0 and j != 0 and j != nyf - 1:
                        seg = seg[margin : seg.shape[0] - margin, 0 : seg.shape[1] - margin]

                        prediction_true[index_y_d + margin : index_y_u - margin, index_x_d + 0 : index_x_u - margin, :] = seg

                    elif i == nxf - 1 and j != 0 and j != nyf - 1:
                        seg = seg[margin : seg.shape[0] - margin, margin : seg.shape[1] - 0]

                        prediction_true[index_y_d + margin : index_y_u - margin, index_x_d + margin : index_x_u - 0, :] = seg

                    elif i != 0 and i != nxf - 1 and j == 0:
                        seg = seg[0 : seg.shape[0] - margin, margin : seg.shape[1] - margin]
                        prediction_true[index_y_d + 0 : index_y_u - margin, index_x_d + margin : index_x_u - margin, :] = seg

                    elif i != 0 and i != nxf - 1 and j == nyf - 1:
                        seg = seg[margin : seg.shape[0] - 0, margin : seg.shape[1] - margin]

                        prediction_true[index_y_d + margin : index_y_u - 0, index_x_d + margin : index_x_u - margin, :] = seg

                    else:
                        seg = seg[margin : seg.shape[0] - margin, margin : seg.shape[1] - margin]

                        prediction_true[index_y_d + margin : index_y_u - margin, index_x_d + margin : index_x_u - margin, :] = seg

            prediction_true = prediction_true.astype(int)

            del model_enhancement
            del session_enhancemnet

            return prediction_true

    def check_dpi(self):
        dpi = os.popen('identify -format "%x " ' + self.image_dir).read()
        return int(float(dpi))

    def resize_image_with_column_classifier(self, is_image_enhanced):
        dpi = self.check_dpi()
        img = cv2.imread(self.image_dir)
        img = img.astype(np.uint8)

        _, page_coord = self.early_page_for_num_of_column_classification()
        model_num_classifier, session_col_classifier = self.start_new_session_and_model(self.model_dir_of_col_classifier)

        img_1ch = cv2.imread(self.image_dir, 0)

        width_early = img_1ch.shape[1]

        img_1ch = img_1ch[page_coord[0] : page_coord[1], page_coord[2] : page_coord[3]]

        # plt.imshow(img_1ch)
        # plt.show()
        img_1ch = img_1ch / 255.0

        img_1ch = cv2.resize(img_1ch, (448, 448), interpolation=cv2.INTER_NEAREST)

        img_in = np.zeros((1, img_1ch.shape[0], img_1ch.shape[1], 3))
        img_in[0, :, :, 0] = img_1ch[:, :]
        img_in[0, :, :, 1] = img_1ch[:, :]
        img_in[0, :, :, 2] = img_1ch[:, :]

        label_p_pred = model_num_classifier.predict(img_in)
        num_col = np.argmax(label_p_pred[0]) + 1

        print(num_col, label_p_pred, "num_col_classifier")

        session_col_classifier.close()
        del model_num_classifier
        del session_col_classifier

        K.clear_session()
        gc.collect()

        # sys.exit()
        if num_col == 1 and width_early < 1100:
            img_w_new = 2000
            img_h_new = int(img.shape[0] / float(img.shape[1]) * 2000)

        elif num_col == 1 and width_early >= 2500:
            img_w_new = 2000
            img_h_new = int(img.shape[0] / float(img.shape[1]) * 2000)
        elif num_col == 1 and width_early >= 1100 and width_early < 2500:
            img_w_new = width_early
            img_h_new = int(img.shape[0] / float(img.shape[1]) * width_early)

        elif num_col == 2 and width_early < 2000:
            img_w_new = 2400
            img_h_new = int(img.shape[0] / float(img.shape[1]) * 2400)

        elif num_col == 2 and width_early >= 3500:
            img_w_new = 2400
            img_h_new = int(img.shape[0] / float(img.shape[1]) * 2400)

        elif num_col == 2 and width_early >= 2000 and width_early < 3500:
            img_w_new = width_early
            img_h_new = int(img.shape[0] / float(img.shape[1]) * width_early)

        elif num_col == 3 and width_early < 2000:
            img_w_new = 3000
            img_h_new = int(img.shape[0] / float(img.shape[1]) * 3000)

        elif num_col == 3 and width_early >= 4000:
            img_w_new = 3000
            img_h_new = int(img.shape[0] / float(img.shape[1]) * 3000)

        elif num_col == 3 and width_early >= 2000 and width_early < 4000:
            img_w_new = width_early
            img_h_new = int(img.shape[0] / float(img.shape[1]) * width_early)

        elif num_col == 4 and width_early < 2500:
            img_w_new = 4000
            img_h_new = int(img.shape[0] / float(img.shape[1]) * 4000)

        elif num_col == 4 and width_early >= 5000:
            img_w_new = 4000
            img_h_new = int(img.shape[0] / float(img.shape[1]) * 4000)

        elif num_col == 4 and width_early >= 2500 and width_early < 5000:
            img_w_new = width_early
            img_h_new = int(img.shape[0] / float(img.shape[1]) * width_early)

        elif num_col == 5 and width_early < 3700:
            img_w_new = 5000
            img_h_new = int(img.shape[0] / float(img.shape[1]) * 5000)

        elif num_col == 5 and width_early >= 7000:
            img_w_new = 5000
            img_h_new = int(img.shape[0] / float(img.shape[1]) * 5000)

        elif num_col == 5 and width_early >= 3700 and width_early < 7000:
            img_w_new = width_early
            img_h_new = int(img.shape[0] / float(img.shape[1]) * width_early)

        elif num_col == 6 and width_early < 4500:
            img_w_new = 6500  # 5400
            img_h_new = int(img.shape[0] / float(img.shape[1]) * 6500)

        else:
            img_w_new = width_early
            img_h_new = int(img.shape[0] / float(img.shape[1]) * width_early)

        if label_p_pred[0][int(num_col - 1)] < 0.9 and img_w_new < width_early:
            img_new = np.copy(img)
            num_column_is_classified = False
        else:
            img_new = resize_image(img, img_h_new, img_w_new)
            num_column_is_classified = True

        if img_new.shape[1] > img.shape[1]:
            img_new = self.predict_enhancement(img_new)
            is_image_enhanced = True

        return img, img_new, is_image_enhanced

    def resize_and_enhance_image_with_column_classifier(self, is_image_enhanced):
        dpi = self.check_dpi()
        img = cv2.imread(self.image_dir)

        img = img.astype(np.uint8)

        _, page_coord = self.early_page_for_num_of_column_classification()
        model_num_classifier, session_col_classifier = self.start_new_session_and_model(self.model_dir_of_col_classifier)

        img_1ch = cv2.imread(self.image_dir, 0)
        img_1ch = img_1ch.astype(np.uint8)

        width_early = img_1ch.shape[1]

        img_1ch = img_1ch[page_coord[0] : page_coord[1], page_coord[2] : page_coord[3]]

        # plt.imshow(img_1ch)
        # plt.show()
        img_1ch = img_1ch / 255.0

        img_1ch = cv2.resize(img_1ch, (448, 448), interpolation=cv2.INTER_NEAREST)

        img_in = np.zeros((1, img_1ch.shape[0], img_1ch.shape[1], 3))
        img_in[0, :, :, 0] = img_1ch[:, :]
        img_in[0, :, :, 1] = img_1ch[:, :]
        img_in[0, :, :, 2] = img_1ch[:, :]

        # plt.imshow(img_in[0,:,:,:])
        # plt.show()

        label_p_pred = model_num_classifier.predict(img_in)
        num_col = np.argmax(label_p_pred[0]) + 1

        print(num_col, label_p_pred, "num_col_classifier")

        session_col_classifier.close()
        del model_num_classifier
        del session_col_classifier
        del img_in
        del img_1ch
        del page_coord

        K.clear_session()
        gc.collect()

        print(dpi)

        if dpi < 298:

            # sys.exit()
            if num_col == 1 and width_early < 1100:
                img_w_new = 2000
                img_h_new = int(img.shape[0] / float(img.shape[1]) * 2000)

            elif num_col == 1 and width_early >= 2500:
                img_w_new = 2000
                img_h_new = int(img.shape[0] / float(img.shape[1]) * 2000)
            elif num_col == 1 and width_early >= 1100 and width_early < 2500:
                img_w_new = width_early
                img_h_new = int(img.shape[0] / float(img.shape[1]) * width_early)

            elif num_col == 2 and width_early < 2000:
                img_w_new = 2400
                img_h_new = int(img.shape[0] / float(img.shape[1]) * 2400)

            elif num_col == 2 and width_early >= 3500:
                img_w_new = 2400
                img_h_new = int(img.shape[0] / float(img.shape[1]) * 2400)

            elif num_col == 2 and width_early >= 2000 and width_early < 3500:
                img_w_new = width_early
                img_h_new = int(img.shape[0] / float(img.shape[1]) * width_early)

            elif num_col == 3 and width_early < 2000:
                img_w_new = 3000
                img_h_new = int(img.shape[0] / float(img.shape[1]) * 3000)

            elif num_col == 3 and width_early >= 4000:
                img_w_new = 3000
                img_h_new = int(img.shape[0] / float(img.shape[1]) * 3000)

            elif num_col == 3 and width_early >= 2000 and width_early < 4000:
                img_w_new = width_early
                img_h_new = int(img.shape[0] / float(img.shape[1]) * width_early)

            elif num_col == 4 and width_early < 2500:
                img_w_new = 4000
                img_h_new = int(img.shape[0] / float(img.shape[1]) * 4000)

            elif num_col == 4 and width_early >= 5000:
                img_w_new = 4000
                img_h_new = int(img.shape[0] / float(img.shape[1]) * 4000)

            elif num_col == 4 and width_early >= 2500 and width_early < 5000:
                img_w_new = width_early
                img_h_new = int(img.shape[0] / float(img.shape[1]) * width_early)

            elif num_col == 5 and width_early < 3700:
                img_w_new = 5000
                img_h_new = int(img.shape[0] / float(img.shape[1]) * 5000)

            elif num_col == 5 and width_early >= 7000:
                img_w_new = 5000
                img_h_new = int(img.shape[0] / float(img.shape[1]) * 5000)

            elif num_col == 5 and width_early >= 3700 and width_early < 7000:
                img_w_new = width_early
                img_h_new = int(img.shape[0] / float(img.shape[1]) * width_early)

            elif num_col == 6 and width_early < 4500:
                img_w_new = 6500  # 5400
                img_h_new = int(img.shape[0] / float(img.shape[1]) * 6500)

            else:
                img_w_new = width_early
                img_h_new = int(img.shape[0] / float(img.shape[1]) * width_early)

            if label_p_pred[0][int(num_col - 1)] < 0.9 and img_w_new < width_early:
                img_new = np.copy(img)
                num_column_is_classified = False
            else:
                img_new = resize_image(img, img_h_new, img_w_new)
                num_column_is_classified = True

            # img_new=resize_image(img,img_h_new,img_w_new)
            image_res = self.predict_enhancement(img_new)
            # cv2.imwrite(os.path.join(self.dir_out, self.f_name) + ".tif",self.image)
            # self.image=self.image.astype(np.uint16)

            # self.scale_x=1
            # self.scale_y=1
            # self.height_org = self.image.shape[0]
            # self.width_org = self.image.shape[1]
            is_image_enhanced = True
        else:
            """
            if img.shape[0]<=2530 and img.shape[0]>=img.shape[1]:
                img_h_new=3000
                img_w_new=int(img.shape[1]/float(img.shape[0]) * 3000)
                img_new=resize_image(img,img_h_new,img_w_new)
                image_res=self.predict_enhancement(img_new)
                #cv2.imwrite(os.path.join(self.dir_out, self.f_name) + ".tif",self.image)
                #self.image=self.image.astype(np.uint16)
                ##self.scale_x=1
                ##self.scale_y=1
                ##self.height_org = self.image.shape[0]
                ##self.width_org = self.image.shape[1]
                is_image_enhanced=True
            else:
                is_image_enhanced=False
                image_res=np.copy(img)

            """
            is_image_enhanced = False
            num_column_is_classified = True
            image_res = np.copy(img)

        return is_image_enhanced, img, image_res, num_col, num_column_is_classified

    def get_image_and_scales(self, img_org, img_res, scale):
        self.image = np.copy(img_res)
        self.image_org = np.copy(img_org)
        self.height_org = self.image.shape[0]
        self.width_org = self.image.shape[1]

        self.img_hight_int = int(self.image.shape[0] * scale)
        self.img_width_int = int(self.image.shape[1] * scale)
        self.scale_y = self.img_hight_int / float(self.image.shape[0])
        self.scale_x = self.img_width_int / float(self.image.shape[1])

        self.image = resize_image(self.image, self.img_hight_int, self.img_width_int)
        del img_res
        del img_org

    def get_image_and_scales_after_enhancing(self, img_org, img_res):

        # self.image = cv2.imread(self.image_dir)

        self.image = np.copy(img_res)
        self.image = self.image.astype(np.uint8)
        self.image_org = np.copy(img_org)
        self.height_org = self.image_org.shape[0]
        self.width_org = self.image_org.shape[1]

        self.scale_y = img_res.shape[0] / float(self.image_org.shape[0])
        self.scale_x = img_res.shape[1] / float(self.image_org.shape[1])

        del img_org
        del img_res

    def start_new_session_and_model(self, model_dir):
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True

        session = tf.InteractiveSession()
        model = load_model(model_dir, compile=False)

        return model, session


    def do_prediction(self, patches, img, model, marginal_of_patch_percent=0.1):

        img_height_model = model.layers[len(model.layers) - 1].output_shape[1]
        img_width_model = model.layers[len(model.layers) - 1].output_shape[2]
        n_classes = model.layers[len(model.layers) - 1].output_shape[3]

        if patches:
            if img.shape[0] < img_height_model:
                img = resize_image(img, img_height_model, img.shape[1])

            if img.shape[1] < img_width_model:
                img = resize_image(img, img.shape[0], img_width_model)

            # print(img_height_model,img_width_model)
            # margin = int(0.2 * img_width_model)
            margin = int(marginal_of_patch_percent * img_height_model)

            width_mid = img_width_model - 2 * margin
            height_mid = img_height_model - 2 * margin

            img = img / float(255.0)
            # print(sys.getsizeof(img))
            # print(np.max(img))

            img = img.astype(np.float16)

            # print(sys.getsizeof(img))

            img_h = img.shape[0]
            img_w = img.shape[1]

            prediction_true = np.zeros((img_h, img_w, 3))
            mask_true = np.zeros((img_h, img_w))
            nxf = img_w / float(width_mid)
            nyf = img_h / float(height_mid)

            if nxf > int(nxf):
                nxf = int(nxf) + 1
            else:
                nxf = int(nxf)

            if nyf > int(nyf):
                nyf = int(nyf) + 1
            else:
                nyf = int(nyf)

            for i in range(nxf):
                for j in range(nyf):

                    if i == 0:
                        index_x_d = i * width_mid
                        index_x_u = index_x_d + img_width_model
                    elif i > 0:
                        index_x_d = i * width_mid
                        index_x_u = index_x_d + img_width_model

                    if j == 0:
                        index_y_d = j * height_mid
                        index_y_u = index_y_d + img_height_model
                    elif j > 0:
                        index_y_d = j * height_mid
                        index_y_u = index_y_d + img_height_model

                    if index_x_u > img_w:
                        index_x_u = img_w
                        index_x_d = img_w - img_width_model
                    if index_y_u > img_h:
                        index_y_u = img_h
                        index_y_d = img_h - img_height_model

                    img_patch = img[index_y_d:index_y_u, index_x_d:index_x_u, :]

                    label_p_pred = model.predict(img_patch.reshape(1, img_patch.shape[0], img_patch.shape[1], img_patch.shape[2]))

                    seg = np.argmax(label_p_pred, axis=3)[0]

                    seg_color = np.repeat(seg[:, :, np.newaxis], 3, axis=2)

                    if i == 0 and j == 0:
                        seg_color = seg_color[0 : seg_color.shape[0] - margin, 0 : seg_color.shape[1] - margin, :]
                        seg = seg[0 : seg.shape[0] - margin, 0 : seg.shape[1] - margin]

                        mask_true[index_y_d + 0 : index_y_u - margin, index_x_d + 0 : index_x_u - margin] = seg
                        prediction_true[index_y_d + 0 : index_y_u - margin, index_x_d + 0 : index_x_u - margin, :] = seg_color

                    elif i == nxf - 1 and j == nyf - 1:
                        seg_color = seg_color[margin : seg_color.shape[0] - 0, margin : seg_color.shape[1] - 0, :]
                        seg = seg[margin : seg.shape[0] - 0, margin : seg.shape[1] - 0]

                        mask_true[index_y_d + margin : index_y_u - 0, index_x_d + margin : index_x_u - 0] = seg
                        prediction_true[index_y_d + margin : index_y_u - 0, index_x_d + margin : index_x_u - 0, :] = seg_color

                    elif i == 0 and j == nyf - 1:
                        seg_color = seg_color[margin : seg_color.shape[0] - 0, 0 : seg_color.shape[1] - margin, :]
                        seg = seg[margin : seg.shape[0] - 0, 0 : seg.shape[1] - margin]

                        mask_true[index_y_d + margin : index_y_u - 0, index_x_d + 0 : index_x_u - margin] = seg
                        prediction_true[index_y_d + margin : index_y_u - 0, index_x_d + 0 : index_x_u - margin, :] = seg_color

                    elif i == nxf - 1 and j == 0:
                        seg_color = seg_color[0 : seg_color.shape[0] - margin, margin : seg_color.shape[1] - 0, :]
                        seg = seg[0 : seg.shape[0] - margin, margin : seg.shape[1] - 0]

                        mask_true[index_y_d + 0 : index_y_u - margin, index_x_d + margin : index_x_u - 0] = seg
                        prediction_true[index_y_d + 0 : index_y_u - margin, index_x_d + margin : index_x_u - 0, :] = seg_color

                    elif i == 0 and j != 0 and j != nyf - 1:
                        seg_color = seg_color[margin : seg_color.shape[0] - margin, 0 : seg_color.shape[1] - margin, :]
                        seg = seg[margin : seg.shape[0] - margin, 0 : seg.shape[1] - margin]

                        mask_true[index_y_d + margin : index_y_u - margin, index_x_d + 0 : index_x_u - margin] = seg
                        prediction_true[index_y_d + margin : index_y_u - margin, index_x_d + 0 : index_x_u - margin, :] = seg_color

                    elif i == nxf - 1 and j != 0 and j != nyf - 1:
                        seg_color = seg_color[margin : seg_color.shape[0] - margin, margin : seg_color.shape[1] - 0, :]
                        seg = seg[margin : seg.shape[0] - margin, margin : seg.shape[1] - 0]

                        mask_true[index_y_d + margin : index_y_u - margin, index_x_d + margin : index_x_u - 0] = seg
                        prediction_true[index_y_d + margin : index_y_u - margin, index_x_d + margin : index_x_u - 0, :] = seg_color

                    elif i != 0 and i != nxf - 1 and j == 0:
                        seg_color = seg_color[0 : seg_color.shape[0] - margin, margin : seg_color.shape[1] - margin, :]
                        seg = seg[0 : seg.shape[0] - margin, margin : seg.shape[1] - margin]

                        mask_true[index_y_d + 0 : index_y_u - margin, index_x_d + margin : index_x_u - margin] = seg
                        prediction_true[index_y_d + 0 : index_y_u - margin, index_x_d + margin : index_x_u - margin, :] = seg_color

                    elif i != 0 and i != nxf - 1 and j == nyf - 1:
                        seg_color = seg_color[margin : seg_color.shape[0] - 0, margin : seg_color.shape[1] - margin, :]
                        seg = seg[margin : seg.shape[0] - 0, margin : seg.shape[1] - margin]

                        mask_true[index_y_d + margin : index_y_u - 0, index_x_d + margin : index_x_u - margin] = seg
                        prediction_true[index_y_d + margin : index_y_u - 0, index_x_d + margin : index_x_u - margin, :] = seg_color

                    else:
                        seg_color = seg_color[margin : seg_color.shape[0] - margin, margin : seg_color.shape[1] - margin, :]
                        seg = seg[margin : seg.shape[0] - margin, margin : seg.shape[1] - margin]

                        mask_true[index_y_d + margin : index_y_u - margin, index_x_d + margin : index_x_u - margin] = seg
                        prediction_true[index_y_d + margin : index_y_u - margin, index_x_d + margin : index_x_u - margin, :] = seg_color

            prediction_true = prediction_true.astype(np.uint8)
            del img
            del mask_true
            del seg_color
            del seg
            del img_patch

        if not patches:
            img_h_page = img.shape[0]
            img_w_page = img.shape[1]
            img = img / float(255.0)
            img = resize_image(img, img_height_model, img_width_model)

            label_p_pred = model.predict(img.reshape(1, img.shape[0], img.shape[1], img.shape[2]))

            seg = np.argmax(label_p_pred, axis=3)[0]
            seg_color = np.repeat(seg[:, :, np.newaxis], 3, axis=2)
            prediction_true = resize_image(seg_color, img_h_page, img_w_page)
            prediction_true = prediction_true.astype(np.uint8)

            del img
            del seg_color
            del label_p_pred
            del seg
        del model
        gc.collect()

        return prediction_true

    def early_page_for_num_of_column_classification(self):
        img = cv2.imread(self.image_dir)
        img = img.astype(np.uint8)
        patches = False
        model_page, session_page = self.start_new_session_and_model(self.model_page_dir)
        ###img = otsu_copy(self.image)
        for ii in range(1):
            img = cv2.GaussianBlur(img, (5, 5), 0)

        img_page_prediction = self.do_prediction(patches, img, model_page)

        imgray = cv2.cvtColor(img_page_prediction, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(imgray, 0, 255, 0)

        thresh = cv2.dilate(thresh, self.kernel, iterations=3)
        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        cnt_size = np.array([cv2.contourArea(contours[j]) for j in range(len(contours))])

        cnt = contours[np.argmax(cnt_size)]

        x, y, w, h = cv2.boundingRect(cnt)

        box = [x, y, w, h]

        croped_page, page_coord = crop_image_inside_box(box, img)

        session_page.close()
        del model_page
        del session_page
        del contours
        del thresh
        del img
        del cnt_size
        del cnt
        del box
        del x
        del y
        del w
        del h
        del imgray
        del img_page_prediction

        gc.collect()
        return croped_page, page_coord

    def extract_page(self):
        patches = False
        model_page, session_page = self.start_new_session_and_model(self.model_page_dir)
        ###img = otsu_copy(self.image)
        for ii in range(1):
            img = cv2.GaussianBlur(self.image, (5, 5), 0)

        img_page_prediction = self.do_prediction(patches, img, model_page)

        imgray = cv2.cvtColor(img_page_prediction, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(imgray, 0, 255, 0)

        thresh = cv2.dilate(thresh, self.kernel, iterations=3)
        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        cnt_size = np.array([cv2.contourArea(contours[j]) for j in range(len(contours))])

        cnt = contours[np.argmax(cnt_size)]

        x, y, w, h = cv2.boundingRect(cnt)

        if x <= 30:
            w = w + x
            x = 0
        if (self.image.shape[1] - (x + w)) <= 30:
            w = w + (self.image.shape[1] - (x + w))

        if y <= 30:
            h = h + y
            y = 0
        if (self.image.shape[0] - (y + h)) <= 30:
            h = h + (self.image.shape[0] - (y + h))

        box = [x, y, w, h]

        croped_page, page_coord = crop_image_inside_box(box, self.image)

        self.cont_page = []
        self.cont_page.append(np.array([[page_coord[2], page_coord[0]], [page_coord[3], page_coord[0]], [page_coord[3], page_coord[1]], [page_coord[2], page_coord[1]]]))

        session_page.close()
        del model_page
        del session_page
        del contours
        del thresh
        del img
        del imgray

        gc.collect()
        return croped_page, page_coord

    def extract_text_regions(self, img, patches, cols):
        img_height_h = img.shape[0]
        img_width_h = img.shape[1]

        ###if patches and cols>=3 :
        ###model_region, session_region = self.start_new_session_and_model(self.model_region_dir_fully)
        ###if not patches:
        ###model_region, session_region = self.start_new_session_and_model(self.model_region_dir_fully_np)

        ###if patches and cols==2 :
        ###model_region, session_region = self.start_new_session_and_model(self.model_region_dir_p_2col)

        ###if patches and cols==1 :
        ###model_region, session_region = self.start_new_session_and_model(self.model_region_dir_p_2col)

        ###if patches and cols>=2:

        ###img = otsu_copy_binary(img)#otsu_copy(img)
        ###img = img.astype(np.uint8)

        ###if patches and cols==1:

        ###img = otsu_copy_binary(img)#otsu_copy(img)
        ###img = img.astype(np.uint8)
        ###img= resize_image(img, int(img_height_h*1), int(img_width_h*1) )

        if patches:
            model_region, session_region = self.start_new_session_and_model(self.model_region_dir_fully)
        if not patches:
            model_region, session_region = self.start_new_session_and_model(self.model_region_dir_fully_np)

        if patches and cols == 1:
            img2 = otsu_copy_binary(img)  # otsu_copy(img)
            img2 = img2.astype(np.uint8)
            img2 = resize_image(img2, int(img_height_h * 0.7), int(img_width_h * 0.7))

            marginal_of_patch_percent = 0.1
            prediction_regions2 = self.do_prediction(patches, img2, model_region, marginal_of_patch_percent)
            prediction_regions2 = resize_image(prediction_regions2, img_height_h, img_width_h)

        if patches and cols == 2:
            img2 = otsu_copy_binary(img)  # otsu_copy(img)
            img2 = img2.astype(np.uint8)
            img2 = resize_image(img2, int(img_height_h * 0.4), int(img_width_h * 0.4))

            marginal_of_patch_percent = 0.1
            prediction_regions2 = self.do_prediction(patches, img2, model_region, marginal_of_patch_percent)
            prediction_regions2 = resize_image(prediction_regions2, img_height_h, img_width_h)
        elif patches and cols > 2:
            img2 = otsu_copy_binary(img)  # otsu_copy(img)
            img2 = img2.astype(np.uint8)
            img2 = resize_image(img2, int(img_height_h * 0.3), int(img_width_h * 0.3))

            marginal_of_patch_percent = 0.1
            prediction_regions2 = self.do_prediction(patches, img2, model_region, marginal_of_patch_percent)
            prediction_regions2 = resize_image(prediction_regions2, img_height_h, img_width_h)

        if patches and cols == 2:
            img = otsu_copy_binary(img)  # otsu_copy(img)

            img = img.astype(np.uint8)

            if img_width_h >= 2000:
                img = resize_image(img, int(img_height_h * 0.9), int(img_width_h * 0.9))
            else:
                pass  # img= resize_image(img, int(img_height_h*1), int(img_width_h*1) )
            img = img.astype(np.uint8)

        if patches and cols == 1:
            img = otsu_copy_binary(img)  # otsu_copy(img)

            img = img.astype(np.uint8)
            img = resize_image(img, int(img_height_h * 0.5), int(img_width_h * 0.5))
            img = img.astype(np.uint8)

        if patches and cols == 3:

            img = otsu_copy_binary(img)  # otsu_copy(img)
            img = img.astype(np.uint8)
            # img= resize_image(img, int(img_height_h*0.9), int(img_width_h*0.9) )

        if patches and cols == 4:

            img = otsu_copy_binary(img)  # otsu_copy(img)
            img = img.astype(np.uint8)
            # img= resize_image(img, int(img_height_h*0.9), int(img_width_h*0.9) )

        if patches and cols >= 5:

            img = otsu_copy_binary(img)  # otsu_copy(img)
            img = img.astype(np.uint8)
            # img= resize_image(img, int(img_height_h*0.9), int(img_width_h*0.9) )

        if not patches:
            img = otsu_copy_binary(img)  # otsu_copy(img)
            img = img.astype(np.uint8)
            prediction_regions2 = None

        marginal_of_patch_percent = 0.1
        prediction_regions = self.do_prediction(patches, img, model_region, marginal_of_patch_percent)
        prediction_regions = resize_image(prediction_regions, img_height_h, img_width_h)

        session_region.close()
        del model_region
        del session_region
        del img
        gc.collect()
        return prediction_regions, prediction_regions2

    def get_slopes_and_deskew_new(self, contours, contours_par, textline_mask_tot, image_page_rotated, boxes, slope_deskew):
        num_cores = cpu_count()
        queue_of_all_params = Queue()

        processes = []
        nh = np.linspace(0, len(boxes), num_cores + 1)
        indexes_by_text_con = np.array(range(len(contours_par)))

        for i in range(num_cores):
            boxes_per_process = boxes[int(nh[i]) : int(nh[i + 1])]
            contours_per_process = contours[int(nh[i]) : int(nh[i + 1])]
            contours_par_per_process = contours_par[int(nh[i]) : int(nh[i + 1])]
            indexes_text_con_per_process = indexes_by_text_con[int(nh[i]) : int(nh[i + 1])]

            processes.append(Process(target=self.do_work_of_slopes_new, args=(queue_of_all_params, boxes_per_process, textline_mask_tot, contours_per_process, contours_par_per_process, indexes_text_con_per_process, image_page_rotated, slope_deskew)))

        for i in range(num_cores):
            processes[i].start()

        slopes = []
        all_found_texline_polygons = []
        all_found_text_regions = []
        all_found_text_regions_par = []
        boxes = []
        all_box_coord = []
        all_index_text_con = []

        for i in range(num_cores):
            list_all_par = queue_of_all_params.get(True)

            slopes_for_sub_process = list_all_par[0]
            polys_for_sub_process = list_all_par[1]
            boxes_for_sub_process = list_all_par[2]
            contours_for_subprocess = list_all_par[3]
            contours_par_for_subprocess = list_all_par[4]
            boxes_coord_for_subprocess = list_all_par[5]
            indexes_for_subprocess = list_all_par[6]

            for j in range(len(slopes_for_sub_process)):
                slopes.append(slopes_for_sub_process[j])
                all_found_texline_polygons.append(polys_for_sub_process[j])
                boxes.append(boxes_for_sub_process[j])
                all_found_text_regions.append(contours_for_subprocess[j])
                all_found_text_regions_par.append(contours_par_for_subprocess[j])
                all_box_coord.append(boxes_coord_for_subprocess[j])
                all_index_text_con.append(indexes_for_subprocess[j])

        for i in range(num_cores):
            processes[i].join()
        # print(slopes,'slopes')
        return slopes, all_found_texline_polygons, boxes, all_found_text_regions, all_found_text_regions_par, all_box_coord, all_index_text_con

    def get_slopes_and_deskew_new_curved(self, contours, contours_par, textline_mask_tot, image_page_rotated, boxes, mask_texts_only, num_col, scale_par, slope_deskew):
        num_cores = cpu_count()
        queue_of_all_params = Queue()

        processes = []
        nh = np.linspace(0, len(boxes), num_cores + 1)
        indexes_by_text_con = np.array(range(len(contours_par)))

        for i in range(num_cores):
            boxes_per_process = boxes[int(nh[i]) : int(nh[i + 1])]
            contours_per_process = contours[int(nh[i]) : int(nh[i + 1])]
            contours_par_per_process = contours_par[int(nh[i]) : int(nh[i + 1])]
            indexes_text_con_per_process = indexes_by_text_con[int(nh[i]) : int(nh[i + 1])]

            processes.append(Process(target=self.do_work_of_slopes_new_curved, args=(queue_of_all_params, boxes_per_process, textline_mask_tot, contours_per_process, contours_par_per_process, image_page_rotated, mask_texts_only, num_col, scale_par, indexes_text_con_per_process, slope_deskew)))

        for i in range(num_cores):
            processes[i].start()

        slopes = []
        all_found_texline_polygons = []
        all_found_text_regions = []
        all_found_text_regions_par = []
        boxes = []
        all_box_coord = []
        all_index_text_con = []

        for i in range(num_cores):
            list_all_par = queue_of_all_params.get(True)

            polys_for_sub_process = list_all_par[0]
            boxes_for_sub_process = list_all_par[1]
            contours_for_subprocess = list_all_par[2]
            contours_par_for_subprocess = list_all_par[3]
            boxes_coord_for_subprocess = list_all_par[4]
            indexes_for_subprocess = list_all_par[5]
            slopes_for_sub_process = list_all_par[6]

            for j in range(len(polys_for_sub_process)):
                slopes.append(slopes_for_sub_process[j])
                all_found_texline_polygons.append(polys_for_sub_process[j])
                boxes.append(boxes_for_sub_process[j])
                all_found_text_regions.append(contours_for_subprocess[j])
                all_found_text_regions_par.append(contours_par_for_subprocess[j])
                all_box_coord.append(boxes_coord_for_subprocess[j])
                all_index_text_con.append(indexes_for_subprocess[j])

        for i in range(num_cores):
            processes[i].join()
        # print(slopes,'slopes')
        return all_found_texline_polygons, boxes, all_found_text_regions, all_found_text_regions_par, all_box_coord, all_index_text_con, slopes

    def do_work_of_slopes_new_curved(self, queue_of_all_params, boxes_text, textline_mask_tot_ea, contours_per_process, contours_par_per_process, image_page_rotated, mask_texts_only, num_col, scale_par, indexes_r_con_per_pro, slope_deskew):
        slopes_per_each_subprocess = []
        bounding_box_of_textregion_per_each_subprocess = []
        textlines_rectangles_per_each_subprocess = []
        contours_textregion_per_each_subprocess = []
        contours_textregion_par_per_each_subprocess = []
        all_box_coord_per_process = []
        index_by_text_region_contours = []
        slope_biggest = 0

        textline_cnt_seperated = np.zeros(textline_mask_tot_ea.shape)

        for mv in range(len(boxes_text)):

            all_text_region_raw = textline_mask_tot_ea[boxes_text[mv][1] : boxes_text[mv][1] + boxes_text[mv][3], boxes_text[mv][0] : boxes_text[mv][0] + boxes_text[mv][2]]
            all_text_region_raw = all_text_region_raw.astype(np.uint8)

            img_int_p = all_text_region_raw[:, :]  # self.all_text_region_raw[mv]

            ##img_int_p=cv2.erode(img_int_p,self.kernel,iterations = 2)

            # plt.imshow(img_int_p)
            # plt.show()

            if img_int_p.shape[0] / img_int_p.shape[1] < 0.1:

                slopes_per_each_subprocess.append(0)

                slope_first = 0
                slope_for_all = [slope_deskew][0]

            else:

                try:
                    textline_con, hierachy = return_contours_of_image(img_int_p)
                    textline_con_fil = filter_contours_area_of_image(img_int_p, textline_con, hierachy, max_area=1, min_area=0.0008)
                    y_diff_mean = find_contours_mean_y_diff(textline_con_fil)

                    sigma_des = int(y_diff_mean * (4.0 / 40.0))

                    if sigma_des < 1:
                        sigma_des = 1

                    img_int_p[img_int_p > 0] = 1
                    # slope_for_all=self.return_deskew_slope_new(img_int_p,sigma_des)
                    slope_for_all = return_deskew_slop(img_int_p, sigma_des, dir_of_all=self.dir_of_all, f_name=self.f_name)

                    if abs(slope_for_all) < 0.5:
                        slope_for_all = [slope_deskew][0]
                    # old method
                    # slope_for_all=self.textline_contours_to_get_slope_correctly(self.all_text_region_raw[mv],denoised,contours[mv])
                    # text_patch_processed=textline_contours_postprocessing(gada)

                except:
                    slope_for_all = 999

                ##slope_for_all=return_deskew_slop(img_int_p,sigma_des, dir_of_all=self.dir_of_all, f_name=self.f_name)

                if slope_for_all == 999:
                    slope_for_all = [slope_deskew][0]
                ##if np.abs(slope_for_all)>32.5 and slope_for_all!=999:
                ##slope_for_all=slope_biggest
                ##elif slope_for_all==999:
                ##slope_for_all=slope_biggest
                slopes_per_each_subprocess.append(slope_for_all)

            index_by_text_region_contours.append(indexes_r_con_per_pro[mv])

            crop_img, crop_coor = crop_image_inside_box(boxes_text[mv], image_page_rotated)
            if abs(slope_for_all) < 45:

                # all_box_coord.append(crop_coor)

                textline_region_in_image = np.zeros(textline_mask_tot_ea.shape)
                cnt_o_t_max = contours_par_per_process[mv]

                x, y, w, h = cv2.boundingRect(cnt_o_t_max)

                mask_biggest = np.zeros(mask_texts_only.shape)
                mask_biggest = cv2.fillPoly(mask_biggest, pts=[cnt_o_t_max], color=(1, 1, 1))

                mask_region_in_patch_region = mask_biggest[y : y + h, x : x + w]

                textline_biggest_region = mask_biggest * textline_mask_tot_ea

                # print(slope_for_all,'slope_for_all')
                textline_rotated_seperated = self.seperate_lines_new2(textline_biggest_region[y : y + h, x : x + w], 0, num_col, slope_for_all)

                # new line added
                ##print(np.shape(textline_rotated_seperated),np.shape(mask_biggest))
                textline_rotated_seperated[mask_region_in_patch_region[:, :] != 1] = 0
                # till here

                textline_cnt_seperated[y : y + h, x : x + w] = textline_rotated_seperated
                textline_region_in_image[y : y + h, x : x + w] = textline_rotated_seperated

                # plt.imshow(textline_region_in_image)
                # plt.show()

                # plt.imshow(textline_cnt_seperated)
                # plt.show()

                pixel_img = 1
                cnt_textlines_in_image = return_contours_of_interested_textline(textline_region_in_image, pixel_img)

                textlines_cnt_per_region = []
                for jjjj in range(len(cnt_textlines_in_image)):
                    mask_biggest2 = np.zeros(mask_texts_only.shape)
                    mask_biggest2 = cv2.fillPoly(mask_biggest2, pts=[cnt_textlines_in_image[jjjj]], color=(1, 1, 1))
                    if num_col + 1 == 1:
                        mask_biggest2 = cv2.dilate(mask_biggest2, self.kernel, iterations=5)
                    else:

                        mask_biggest2 = cv2.dilate(mask_biggest2, self.kernel, iterations=4)

                    pixel_img = 1

                    mask_biggest2 = resize_image(mask_biggest2, int(mask_biggest2.shape[0] * scale_par), int(mask_biggest2.shape[1] * scale_par))

                    cnt_textlines_in_image_ind = return_contours_of_interested_textline(mask_biggest2, pixel_img)

                    try:
                        # textlines_cnt_per_region.append(cnt_textlines_in_image_ind[0]/scale_par)
                        textlines_cnt_per_region.append(cnt_textlines_in_image_ind[0])
                    except:
                        pass

            else:
                slope_first = 0
                add_boxes_coor_into_textlines = True
                textlines_cnt_per_region = textline_contours_postprocessing(all_text_region_raw, slope_for_all, contours_par_per_process[mv], boxes_text[mv], slope_first, add_boxes_coor_into_textlines)
                add_boxes_coor_into_textlines = False
                # print(np.shape(textlines_cnt_per_region),'textlines_cnt_per_region')

            # textlines_cnt_tot_per_process.append(textlines_cnt_per_region)
            # index_polygons_per_process_per_process.append(index_polygons_per_process[iiii])

            textlines_rectangles_per_each_subprocess.append(textlines_cnt_per_region)
            # all_found_texline_polygons.append(cnt_clean_rot)
            bounding_box_of_textregion_per_each_subprocess.append(boxes_text[mv])

            contours_textregion_per_each_subprocess.append(contours_per_process[mv])
            contours_textregion_par_per_each_subprocess.append(contours_par_per_process[mv])
            all_box_coord_per_process.append(crop_coor)

        queue_of_all_params.put([textlines_rectangles_per_each_subprocess, bounding_box_of_textregion_per_each_subprocess, contours_textregion_per_each_subprocess, contours_textregion_par_per_each_subprocess, all_box_coord_per_process, index_by_text_region_contours, slopes_per_each_subprocess])

    def do_work_of_slopes_new(self, queue_of_all_params, boxes_text, textline_mask_tot_ea, contours_per_process, contours_par_per_process, indexes_r_con_per_pro, image_page_rotated, slope_deskew):

        slopes_per_each_subprocess = []
        bounding_box_of_textregion_per_each_subprocess = []
        textlines_rectangles_per_each_subprocess = []
        contours_textregion_per_each_subprocess = []
        contours_textregion_par_per_each_subprocess = []
        all_box_coord_per_process = []
        index_by_text_region_contours = []
        slope_biggest = 0

        for mv in range(len(boxes_text)):

            crop_img, crop_coor = crop_image_inside_box(boxes_text[mv], image_page_rotated)

            # all_box_coord.append(crop_coor)
            
            mask_textline=np.zeros((textline_mask_tot_ea.shape))
            
            mask_textline=cv2.fillPoly(mask_textline,pts=[contours_per_process[mv]],color=(1,1,1))
            
            

            denoised = None
            all_text_region_raw=(textline_mask_tot_ea*mask_textline[:,:])[boxes_text[mv][1]:boxes_text[mv][1]+boxes_text[mv][3] , boxes_text[mv][0]:boxes_text[mv][0]+boxes_text[mv][2] ]
            all_text_region_raw = all_text_region_raw.astype(np.uint8)

            img_int_p = all_text_region_raw[:, :]  # self.all_text_region_raw[mv]

            img_int_p = cv2.erode(img_int_p, self.kernel, iterations=2)

            if img_int_p.shape[0] / img_int_p.shape[1] < 0.1:

                slopes_per_each_subprocess.append(0)

                slope_for_all = [slope_deskew][0]

                all_text_region_raw = textline_mask_tot_ea[boxes_text[mv][1] : boxes_text[mv][1] + boxes_text[mv][3], boxes_text[mv][0] : boxes_text[mv][0] + boxes_text[mv][2]]
                ###cnt_clean_rot=textline_contours_postprocessing(all_text_region_raw,slopes[jj],contours_only_text_parent[jj],boxes_text[jj],slope_first)
                cnt_clean_rot = textline_contours_postprocessing(all_text_region_raw, slope_for_all, contours_par_per_process[mv], boxes_text[mv], 0)

                textlines_rectangles_per_each_subprocess.append(cnt_clean_rot)

                index_by_text_region_contours.append(indexes_r_con_per_pro[mv])
                # all_found_texline_polygons.append(cnt_clean_rot)
                bounding_box_of_textregion_per_each_subprocess.append(boxes_text[mv])
            else:

                try:
                    textline_con, hierachy = return_contours_of_image(img_int_p)
                    textline_con_fil = filter_contours_area_of_image(img_int_p, textline_con, hierachy, max_area=1, min_area=0.00008)

                    y_diff_mean = find_contours_mean_y_diff(textline_con_fil)

                    sigma_des = int(y_diff_mean * (4.0 / 40.0))

                    if sigma_des < 1:
                        sigma_des = 1

                    img_int_p[img_int_p > 0] = 1
                    # slope_for_all=self.return_deskew_slope_new(img_int_p,sigma_des)
                    slope_for_all = return_deskew_slop(img_int_p, sigma_des, dir_of_all=self.dir_of_all, f_name=self.f_name)

                    if abs(slope_for_all) <= 0.5:
                        slope_for_all = [slope_deskew][0]

                except:
                    slope_for_all = 999

                ##slope_for_all=return_deskew_slop(img_int_p,sigma_des, dir_of_all=self.dir_of_all, f_name=self.f_name)

                if slope_for_all == 999:
                    slope_for_all = [slope_deskew][0]
                ##if np.abs(slope_for_all)>32.5 and slope_for_all!=999:
                ##slope_for_all=slope_biggest
                ##elif slope_for_all==999:
                ##slope_for_all=slope_biggest
                slopes_per_each_subprocess.append(slope_for_all)

                slope_first = 0

                mask_only_con_region = np.zeros(textline_mask_tot_ea.shape)
                mask_only_con_region = cv2.fillPoly(mask_only_con_region, pts=[contours_par_per_process[mv]], color=(1, 1, 1))

                # plt.imshow(mask_only_con_region)
                # plt.show()
                all_text_region_raw = np.copy(textline_mask_tot_ea[boxes_text[mv][1] : boxes_text[mv][1] + boxes_text[mv][3], boxes_text[mv][0] : boxes_text[mv][0] + boxes_text[mv][2]])
                mask_only_con_region = mask_only_con_region[boxes_text[mv][1] : boxes_text[mv][1] + boxes_text[mv][3], boxes_text[mv][0] : boxes_text[mv][0] + boxes_text[mv][2]]

                ##plt.imshow(textline_mask_tot_ea)
                ##plt.show()
                ##plt.imshow(all_text_region_raw)
                ##plt.show()

                ##plt.imshow(mask_only_con_region)
                ##plt.show()

                all_text_region_raw[mask_only_con_region == 0] = 0
                ###cnt_clean_rot=textline_contours_postprocessing(all_text_region_raw,slopes[jj],contours_only_text_parent[jj],boxes_text[jj],slope_first)
                cnt_clean_rot = textline_contours_postprocessing(all_text_region_raw, slope_for_all, contours_par_per_process[mv], boxes_text[mv], slope_first)

                textlines_rectangles_per_each_subprocess.append(cnt_clean_rot)
                index_by_text_region_contours.append(indexes_r_con_per_pro[mv])
                # all_found_texline_polygons.append(cnt_clean_rot)
                bounding_box_of_textregion_per_each_subprocess.append(boxes_text[mv])

            contours_textregion_per_each_subprocess.append(contours_per_process[mv])
            contours_textregion_par_per_each_subprocess.append(contours_par_per_process[mv])
            all_box_coord_per_process.append(crop_coor)

        queue_of_all_params.put([slopes_per_each_subprocess, textlines_rectangles_per_each_subprocess, bounding_box_of_textregion_per_each_subprocess, contours_textregion_per_each_subprocess, contours_textregion_par_per_each_subprocess, all_box_coord_per_process, index_by_text_region_contours])

    def textline_contours(self, img, patches, scaler_h, scaler_w):

        if patches:
            model_textline, session_textline = self.start_new_session_and_model(self.model_textline_dir)
        if not patches:
            model_textline, session_textline = self.start_new_session_and_model(self.model_textline_dir_np)

        ##img = otsu_copy(img)
        img = img.astype(np.uint8)

        img_org = np.copy(img)
        img_h = img_org.shape[0]
        img_w = img_org.shape[1]

        img = resize_image(img_org, int(img_org.shape[0] * scaler_h), int(img_org.shape[1] * scaler_w))

        prediction_textline = self.do_prediction(patches, img, model_textline)

        prediction_textline = resize_image(prediction_textline, img_h, img_w)

        patches = False
        prediction_textline_longshot = self.do_prediction(patches, img, model_textline)

        prediction_textline_longshot_true_size = resize_image(prediction_textline_longshot, img_h, img_w)

        # scaler_w=1.5
        # scaler_h=1.5
        # patches=True
        # img= resize_image(img_org, int(img_org.shape[0]*scaler_h), int(img_org.shape[1]*scaler_w))

        # prediction_textline_streched=self.do_prediction(patches,img,model_textline)

        # prediction_textline_streched= resize_image(prediction_textline_streched, img_h, img_w)

        ##plt.imshow(prediction_textline_streched[:,:,0])
        ##plt.show()

        # sys.exit()
        session_textline.close()

        del model_textline
        del session_textline
        del img
        del img_org

        gc.collect()
        return prediction_textline[:, :, 0], prediction_textline_longshot_true_size[:, :, 0]

    def seperate_lines_new(self, img_path, thetha, num_col):

        if num_col == 1:
            num_patches = int(img_path.shape[1] / 200.0)
        else:
            num_patches = int(img_path.shape[1] / 100.0)
        # num_patches=int(img_path.shape[1]/200.)
        if num_patches == 0:
            num_patches = 1
        (h, w) = img_path.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, -thetha, 1.0)
        x_d = M[0, 2]
        y_d = M[1, 2]

        thetha = thetha / 180.0 * np.pi
        rotation_matrix = np.array([[np.cos(thetha), -np.sin(thetha)], [np.sin(thetha), np.cos(thetha)]])

        x_min_cont = 0
        x_max_cont = img_path.shape[1]
        y_min_cont = 0
        y_max_cont = img_path.shape[0]

        xv = np.linspace(x_min_cont, x_max_cont, 1000)

        mada_n = img_path.sum(axis=1)

        ##plt.plot(mada_n)
        ##plt.show()
        first_nonzero = 0  # (next((i for i, x in enumerate(mada_n) if x), None))

        y = mada_n[:]  # [first_nonzero:last_nonzero]
        y_help = np.zeros(len(y) + 40)
        y_help[20 : len(y) + 20] = y
        x = np.array(range(len(y)))

        peaks_real, _ = find_peaks(gaussian_filter1d(y, 3), height=0)
        if len(peaks_real) <= 2 and len(peaks_real) > 1:
            sigma_gaus = 10
        else:
            sigma_gaus = 6

        z = gaussian_filter1d(y_help, sigma_gaus)
        zneg_rev = -y_help + np.max(y_help)
        zneg = np.zeros(len(zneg_rev) + 40)
        zneg[20 : len(zneg_rev) + 20] = zneg_rev
        zneg = gaussian_filter1d(zneg, sigma_gaus)

        peaks, _ = find_peaks(z, height=0)
        peaks_neg, _ = find_peaks(zneg, height=0)

        for nn in range(len(peaks_neg)):
            if peaks_neg[nn] > len(z) - 1:
                peaks_neg[nn] = len(z) - 1
            if peaks_neg[nn] < 0:
                peaks_neg[nn] = 0

        diff_peaks = np.abs(np.diff(peaks_neg))
        cut_off = 20
        peaks_neg_true = []
        forest = []

        for i in range(len(peaks_neg)):
            if i == 0:
                forest.append(peaks_neg[i])
            if i < (len(peaks_neg) - 1):
                if diff_peaks[i] <= cut_off:
                    forest.append(peaks_neg[i + 1])
                if diff_peaks[i] > cut_off:
                    # print(forest[np.argmin(z[forest]) ] )
                    if not isNaN(forest[np.argmin(z[forest])]):
                        # print(len(z),forest)
                        peaks_neg_true.append(forest[np.argmin(z[forest])])
                    forest = []
                    forest.append(peaks_neg[i + 1])
            if i == (len(peaks_neg) - 1):
                # print(print(forest[np.argmin(z[forest]) ] ))
                if not isNaN(forest[np.argmin(z[forest])]):

                    peaks_neg_true.append(forest[np.argmin(z[forest])])

        peaks_neg_true = np.array(peaks_neg_true)

        """
        #plt.figure(figsize=(40,40))
        #plt.subplot(1,2,1)
        #plt.title('Textline segmentation von Textregion')
        #plt.imshow(img_path)
        #plt.xlabel('X')
        #plt.ylabel('Y')
        #plt.subplot(1,2,2)
        #plt.title('Dichte entlang X')
        #base = pyplot.gca().transData
        #rot = transforms.Affine2D().rotate_deg(90)
        #plt.plot(zneg,np.array(range(len(zneg))))
        #plt.plot(zneg[peaks_neg_true],peaks_neg_true,'*')
        #plt.gca().invert_yaxis()

        #plt.xlabel('Dichte')
        #plt.ylabel('Y')
        ##plt.plot([0,len(y)], [grenze,grenze])
        #plt.show()
        """

        peaks_neg_true = peaks_neg_true - 20 - 20
        peaks = peaks - 20

        # dis_up=peaks_neg_true[14]-peaks_neg_true[0]
        # dis_down=peaks_neg_true[18]-peaks_neg_true[14]

        img_patch_ineterst = img_path[:, :]  # [peaks_neg_true[14]-dis_up:peaks_neg_true[15]+dis_down ,:]

        ##plt.imshow(img_patch_ineterst)
        ##plt.show()

        length_x = int(img_path.shape[1] / float(num_patches))
        margin = int(0.04 * length_x)

        width_mid = length_x - 2 * margin

        nxf = img_path.shape[1] / float(width_mid)

        if nxf > int(nxf):
            nxf = int(nxf) + 1
        else:
            nxf = int(nxf)

        slopes_tile_wise = []
        for i in range(nxf):
            if i == 0:
                index_x_d = i * width_mid
                index_x_u = index_x_d + length_x
            elif i > 0:
                index_x_d = i * width_mid
                index_x_u = index_x_d + length_x

            if index_x_u > img_path.shape[1]:
                index_x_u = img_path.shape[1]
                index_x_d = img_path.shape[1] - length_x

            # img_patch = img[index_y_d:index_y_u, index_x_d:index_x_u, :]
            img_xline = img_patch_ineterst[:, index_x_d:index_x_u]

            sigma = 2
            try:
                slope_xline = return_deskew_slop(img_xline, sigma, dir_of_all=self.dir_of_all, f_name=self.f_name)
            except:
                slope_xline = 0
            slopes_tile_wise.append(slope_xline)
            # print(slope_xline,'xlineeee')
            img_line_rotated = rotate_image(img_xline, slope_xline)
            img_line_rotated[:, :][img_line_rotated[:, :] != 0] = 1

        """

        xline=np.linspace(0,img_path.shape[1],nx)
        slopes_tile_wise=[]

        for ui in range( nx-1 ):
            img_xline=img_patch_ineterst[:,int(xline[ui]):int(xline[ui+1])]


            ##plt.imshow(img_xline)
            ##plt.show()

            sigma=3
            try:
                slope_xline=return_deskew_slop(img_xline,sigma, dir_of_all=self.dir_of_all, f_name=self.f_name)
            except:
                slope_xline=0
            slopes_tile_wise.append(slope_xline)
            print(slope_xline,'xlineeee')
            img_line_rotated=rotate_image(img_xline,slope_xline)

            ##plt.imshow(img_line_rotated)
            ##plt.show()
        """

        # dis_up=peaks_neg_true[14]-peaks_neg_true[0]
        # dis_down=peaks_neg_true[18]-peaks_neg_true[14]

        img_patch_ineterst = img_path[:, :]  # [peaks_neg_true[14]-dis_up:peaks_neg_true[14]+dis_down ,:]

        img_patch_ineterst_revised = np.zeros(img_patch_ineterst.shape)

        for i in range(nxf):
            if i == 0:
                index_x_d = i * width_mid
                index_x_u = index_x_d + length_x
            elif i > 0:
                index_x_d = i * width_mid
                index_x_u = index_x_d + length_x

            if index_x_u > img_path.shape[1]:
                index_x_u = img_path.shape[1]
                index_x_d = img_path.shape[1] - length_x

            img_xline = img_patch_ineterst[:, index_x_d:index_x_u]

            img_int = np.zeros((img_xline.shape[0], img_xline.shape[1]))
            img_int[:, :] = img_xline[:, :]  # img_patch_org[:,:,0]

            img_resized = np.zeros((int(img_int.shape[0] * (1.2)), int(img_int.shape[1] * (3))))

            img_resized[int(img_int.shape[0] * (0.1)) : int(img_int.shape[0] * (0.1)) + img_int.shape[0], int(img_int.shape[1] * (1)) : int(img_int.shape[1] * (1)) + img_int.shape[1]] = img_int[:, :]
            ##plt.imshow(img_xline)
            ##plt.show()
            img_line_rotated = rotate_image(img_resized, slopes_tile_wise[i])
            img_line_rotated[:, :][img_line_rotated[:, :] != 0] = 1

            img_patch_seperated = seperate_lines_new_inside_teils(img_line_rotated, 0)

            ##plt.imshow(img_patch_seperated)
            ##plt.show()
            img_patch_seperated_returned = rotate_image(img_patch_seperated, -slopes_tile_wise[i])
            img_patch_seperated_returned[:, :][img_patch_seperated_returned[:, :] != 0] = 1

            img_patch_seperated_returned_true_size = img_patch_seperated_returned[int(img_int.shape[0] * (0.1)) : int(img_int.shape[0] * (0.1)) + img_int.shape[0], int(img_int.shape[1] * (1)) : int(img_int.shape[1] * (1)) + img_int.shape[1]]

            img_patch_seperated_returned_true_size = img_patch_seperated_returned_true_size[:, margin : length_x - margin]
            img_patch_ineterst_revised[:, index_x_d + margin : index_x_u - margin] = img_patch_seperated_returned_true_size

        """
        for ui in range( nx-1 ):
            img_xline=img_patch_ineterst[:,int(xline[ui]):int(xline[ui+1])]


            img_int=np.zeros((img_xline.shape[0],img_xline.shape[1]))
            img_int[:,:]=img_xline[:,:]#img_patch_org[:,:,0]

            img_resized=np.zeros((int( img_int.shape[0]*(1.2) ) , int( img_int.shape[1]*(3) ) ))

            img_resized[ int( img_int.shape[0]*(.1)):int( img_int.shape[0]*(.1))+img_int.shape[0] , int( img_int.shape[1]*(1)):int( img_int.shape[1]*(1))+img_int.shape[1] ]=img_int[:,:]
            ##plt.imshow(img_xline)
            ##plt.show()
            img_line_rotated=rotate_image(img_resized,slopes_tile_wise[ui])


            #img_patch_seperated = seperate_lines_new_inside_teils(img_line_rotated,0)

            img_patch_seperated = seperate_lines_new_inside_teils(img_line_rotated,0)

            img_patch_seperated_returned=rotate_image(img_patch_seperated,-slopes_tile_wise[ui])
            ##plt.imshow(img_patch_seperated)
            ##plt.show()
            print(img_patch_seperated_returned.shape)
            #plt.imshow(img_patch_seperated_returned[ int( img_int.shape[0]*(.1)):int( img_int.shape[0]*(.1))+img_int.shape[0] , int( img_int.shape[1]*(1)):int( img_int.shape[1]*(1))+img_int.shape[1] ])
            #plt.show()

            img_patch_ineterst_revised[:,int(xline[ui]):int(xline[ui+1])]=img_patch_seperated_returned[ int( img_int.shape[0]*(.1)):int( img_int.shape[0]*(.1))+img_int.shape[0] , int( img_int.shape[1]*(1)):int( img_int.shape[1]*(1))+img_int.shape[1] ]


        """

        # print(img_patch_ineterst_revised.shape,np.unique(img_patch_ineterst_revised))
        ##plt.imshow(img_patch_ineterst_revised)
        ##plt.show()
        return img_patch_ineterst_revised

    def seperate_lines_new2(self, img_path, thetha, num_col, slope_region):

        if num_col == 1:
            num_patches = int(img_path.shape[1] / 200.0)
        else:
            num_patches = int(img_path.shape[1] / 140.0)
        # num_patches=int(img_path.shape[1]/200.)
        if num_patches == 0:
            num_patches = 1

        img_patch_ineterst = img_path[:, :]  # [peaks_neg_true[14]-dis_up:peaks_neg_true[15]+dis_down ,:]

        # plt.imshow(img_patch_ineterst)
        # plt.show()

        length_x = int(img_path.shape[1] / float(num_patches))
        # margin = int(0.04 * length_x) just recently this was changed because it break lines into 2
        margin = int(0.04 * length_x)
        # print(margin,'margin')
        # if margin<=4:
        # margin = int(0.08 * length_x)

        # margin=0

        width_mid = length_x - 2 * margin

        nxf = img_path.shape[1] / float(width_mid)

        if nxf > int(nxf):
            nxf = int(nxf) + 1
        else:
            nxf = int(nxf)

        slopes_tile_wise = []
        for i in range(nxf):
            if i == 0:
                index_x_d = i * width_mid
                index_x_u = index_x_d + length_x
            elif i > 0:
                index_x_d = i * width_mid
                index_x_u = index_x_d + length_x

            if index_x_u > img_path.shape[1]:
                index_x_u = img_path.shape[1]
                index_x_d = img_path.shape[1] - length_x

            # img_patch = img[index_y_d:index_y_u, index_x_d:index_x_u, :]
            img_xline = img_patch_ineterst[:, index_x_d:index_x_u]

            sigma = 2
            try:
                slope_xline = return_deskew_slop(img_xline, sigma, dir_of_all=self.dir_of_all, f_name=self.f_name)
            except:
                slope_xline = 0

            if abs(slope_region) < 25 and abs(slope_xline) > 25:
                slope_xline = [slope_region][0]
            # if abs(slope_region)>70 and abs(slope_xline)<25:
            # slope_xline=[slope_region][0]
            slopes_tile_wise.append(slope_xline)
            # print(slope_xline,'xlineeee')
            img_line_rotated = rotate_image(img_xline, slope_xline)
            img_line_rotated[:, :][img_line_rotated[:, :] != 0] = 1

        # print(slopes_tile_wise,'slopes_tile_wise')
        img_patch_ineterst = img_path[:, :]  # [peaks_neg_true[14]-dis_up:peaks_neg_true[14]+dis_down ,:]

        img_patch_ineterst_revised = np.zeros(img_patch_ineterst.shape)

        for i in range(nxf):
            if i == 0:
                index_x_d = i * width_mid
                index_x_u = index_x_d + length_x
            elif i > 0:
                index_x_d = i * width_mid
                index_x_u = index_x_d + length_x

            if index_x_u > img_path.shape[1]:
                index_x_u = img_path.shape[1]
                index_x_d = img_path.shape[1] - length_x

            img_xline = img_patch_ineterst[:, index_x_d:index_x_u]

            img_int = np.zeros((img_xline.shape[0], img_xline.shape[1]))
            img_int[:, :] = img_xline[:, :]  # img_patch_org[:,:,0]

            img_resized = np.zeros((int(img_int.shape[0] * (1.2)), int(img_int.shape[1] * (3))))

            img_resized[int(img_int.shape[0] * (0.1)) : int(img_int.shape[0] * (0.1)) + img_int.shape[0], int(img_int.shape[1] * (1)) : int(img_int.shape[1] * (1)) + img_int.shape[1]] = img_int[:, :]
            # plt.imshow(img_xline)
            # plt.show()
            img_line_rotated = rotate_image(img_resized, slopes_tile_wise[i])
            img_line_rotated[:, :][img_line_rotated[:, :] != 0] = 1

            img_patch_seperated = seperate_lines_new_inside_teils2(img_line_rotated, 0)

            img_patch_seperated_returned = rotate_image(img_patch_seperated, -slopes_tile_wise[i])
            img_patch_seperated_returned[:, :][img_patch_seperated_returned[:, :] != 0] = 1

            img_patch_seperated_returned_true_size = img_patch_seperated_returned[int(img_int.shape[0] * (0.1)) : int(img_int.shape[0] * (0.1)) + img_int.shape[0], int(img_int.shape[1] * (1)) : int(img_int.shape[1] * (1)) + img_int.shape[1]]

            img_patch_seperated_returned_true_size = img_patch_seperated_returned_true_size[:, margin : length_x - margin]
            img_patch_ineterst_revised[:, index_x_d + margin : index_x_u - margin] = img_patch_seperated_returned_true_size

        # plt.imshow(img_patch_ineterst_revised)
        # plt.show()
        return img_patch_ineterst_revised


    def do_work_of_slopes(self, q, poly, box_sub, boxes_per_process, textline_mask_tot, contours_per_process):
        slope_biggest = 0
        slopes_sub = []
        boxes_sub_new = []
        poly_sub = []
        for mv in range(len(boxes_per_process)):

            crop_img, _ = crop_image_inside_box(boxes_per_process[mv], np.repeat(textline_mask_tot[:, :, np.newaxis], 3, axis=2))
            crop_img = crop_img[:, :, 0]
            crop_img = cv2.erode(crop_img, self.kernel, iterations=2)

            try:
                textline_con, hierachy = return_contours_of_image(crop_img)
                textline_con_fil = filter_contours_area_of_image(crop_img, textline_con, hierachy, max_area=1, min_area=0.0008)
                y_diff_mean = find_contours_mean_y_diff(textline_con_fil)

                sigma_des = int(y_diff_mean * (4.0 / 40.0))

                if sigma_des < 1:
                    sigma_des = 1

                crop_img[crop_img > 0] = 1
                slope_corresponding_textregion = return_deskew_slop(crop_img, sigma_des, dir_of_all=self.dir_of_all, f_name=self.f_name)

            except:
                slope_corresponding_textregion = 999

            if slope_corresponding_textregion == 999:
                slope_corresponding_textregion = slope_biggest
            ##if np.abs(slope_corresponding_textregion)>12.5 and slope_corresponding_textregion!=999:
            ##slope_corresponding_textregion=slope_biggest
            ##elif slope_corresponding_textregion==999:
            ##slope_corresponding_textregion=slope_biggest
            slopes_sub.append(slope_corresponding_textregion)

            cnt_clean_rot = textline_contours_postprocessing(crop_img, slope_corresponding_textregion, contours_per_process[mv], boxes_per_process[mv])

            poly_sub.append(cnt_clean_rot)
            boxes_sub_new.append(boxes_per_process[mv])

        q.put(slopes_sub)
        poly.put(poly_sub)
        box_sub.put(boxes_sub_new)

    def write_into_page_xml_full(self, contours, contours_h, page_coord, dir_of_image, order_of_texts, id_of_texts, all_found_texline_polygons, all_found_texline_polygons_h, all_box_coord, all_box_coord_h, found_polygons_text_region_img, found_polygons_tables, found_polygons_drop_capitals, found_polygons_marginals, all_found_texline_polygons_marginals, all_box_coord_marginals, slopes, slopes_marginals):

        found_polygons_text_region = contours
        found_polygons_text_region_h = contours_h

        # create the file structure
        data = ET.Element("PcGts")

        data.set("xmlns", "http://schema.primaresearch.org/PAGE/gts/pagecontent/2017-07-15")
        data.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        data.set("xsi:schemaLocation", "http://schema.primaresearch.org/PAGE/gts/pagecontent/2017-07-15")

        metadata = ET.SubElement(data, "Metadata")

        author = ET.SubElement(metadata, "Creator")
        author.text = "SBB_QURATOR"

        created = ET.SubElement(metadata, "Created")
        created.text = "2019-06-17T18:15:12"

        changetime = ET.SubElement(metadata, "LastChange")
        changetime.text = "2019-06-17T18:15:12"

        page = ET.SubElement(data, "Page")

        page.set("imageFilename", self.image_dir)
        page.set("imageHeight", str(self.height_org))
        page.set("imageWidth", str(self.width_org))
        page.set("type", "content")
        page.set("readingDirection", "left-to-right")
        page.set("textLineOrder", "top-to-bottom")

        page_print_sub = ET.SubElement(page, "PrintSpace")
        coord_page = ET.SubElement(page_print_sub, "Coords")
        points_page_print = ""

        for lmm in range(len(self.cont_page[0])):
            if len(self.cont_page[0][lmm]) == 2:
                points_page_print = points_page_print + str(int((self.cont_page[0][lmm][0]) / self.scale_x))
                points_page_print = points_page_print + ","
                points_page_print = points_page_print + str(int((self.cont_page[0][lmm][1]) / self.scale_y))
            else:
                points_page_print = points_page_print + str(int((self.cont_page[0][lmm][0][0]) / self.scale_x))
                points_page_print = points_page_print + ","
                points_page_print = points_page_print + str(int((self.cont_page[0][lmm][0][1]) / self.scale_y))

            if lmm < (len(self.cont_page[0]) - 1):
                points_page_print = points_page_print + " "
        coord_page.set("points", points_page_print)

        if len(contours) > 0:
            region_order = ET.SubElement(page, "ReadingOrder")
            region_order_sub = ET.SubElement(region_order, "OrderedGroup")

            region_order_sub.set("id", "ro357564684568544579089")

            # args_sort=order_of_texts
            for vj in order_of_texts:
                name = "coord_text_" + str(vj)
                name = ET.SubElement(region_order_sub, "RegionRefIndexed")
                name.set("index", str(order_of_texts[vj]))
                name.set("regionRef", id_of_texts[vj])

            id_of_marginalia = []
            indexer_region = len(contours) + len(contours_h)
            for vm in range(len(found_polygons_marginals)):
                id_of_marginalia.append("r" + str(indexer_region))

                name = "coord_text_" + str(indexer_region)
                name = ET.SubElement(region_order_sub, "RegionRefIndexed")
                name.set("index", str(indexer_region))
                name.set("regionRef", "r" + str(indexer_region))
                indexer_region += 1

            id_indexer = 0
            id_indexer_l = 0

            for mm in range(len(found_polygons_text_region)):
                textregion = ET.SubElement(page, "TextRegion")

                textregion.set("id", "r" + str(id_indexer))
                id_indexer += 1

                textregion.set("type", "paragraph")
                # if mm==0:
                #    textregion.set('type','header')
                # else:
                #    textregion.set('type','paragraph')
                coord_text = ET.SubElement(textregion, "Coords")

                points_co = ""
                for lmm in range(len(found_polygons_text_region[mm])):
                    if len(found_polygons_text_region[mm][lmm]) == 2:
                        points_co = points_co + str(int((found_polygons_text_region[mm][lmm][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_text_region[mm][lmm][1] + page_coord[0]) / self.scale_y))
                    else:
                        points_co = points_co + str(int((found_polygons_text_region[mm][lmm][0][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_text_region[mm][lmm][0][1] + page_coord[0]) / self.scale_y))

                    if lmm < (len(found_polygons_text_region[mm]) - 1):
                        points_co = points_co + " "
                # print(points_co)
                coord_text.set("points", points_co)

                for j in range(len(all_found_texline_polygons[mm])):

                    textline = ET.SubElement(textregion, "TextLine")

                    textline.set("id", "l" + str(id_indexer_l))

                    id_indexer_l += 1

                    coord = ET.SubElement(textline, "Coords")

                    texteq = ET.SubElement(textline, "TextEquiv")

                    uni = ET.SubElement(texteq, "Unicode")
                    uni.text = " "

                    # points = ET.SubElement(coord, 'Points')

                    points_co = ""
                    for l in range(len(all_found_texline_polygons[mm][j])):
                        # point = ET.SubElement(coord, 'Point')

                        if not self.curved_line:
                            # point.set('x',str(found_polygons[j][l][0]))
                            # point.set('y',str(found_polygons[j][l][1]))
                            if len(all_found_texline_polygons[mm][j][l]) == 2:
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0] + all_box_coord[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][1] + all_box_coord[mm][0] + page_coord[0]) / self.scale_y))
                            else:
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0][0] + all_box_coord[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0][1] + all_box_coord[mm][0] + page_coord[0]) / self.scale_y))

                        if (self.curved_line) and np.abs(slopes[mm]) <= 45:
                            if len(all_found_texline_polygons[mm][j][l]) == 2:
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][1] + page_coord[0]) / self.scale_y))
                            else:
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0][0] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0][1] + page_coord[0]) / self.scale_y))
                        elif (self.curved_line) and np.abs(slopes[mm]) > 45:
                            if len(all_found_texline_polygons[mm][j][l]) == 2:
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0] + all_box_coord[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][1] + all_box_coord[mm][0] + page_coord[0]) / self.scale_y))
                            else:
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0][0] + all_box_coord[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0][1] + all_box_coord[mm][0] + page_coord[0]) / self.scale_y))

                        if l < (len(all_found_texline_polygons[mm][j]) - 1):
                            points_co = points_co + " "
                    # print(points_co)
                    coord.set("points", points_co)

                texteqreg = ET.SubElement(textregion, "TextEquiv")

                unireg = ET.SubElement(texteqreg, "Unicode")
                unireg.text = " "

        print(len(contours_h))
        if len(contours_h) > 0:
            for mm in range(len(found_polygons_text_region_h)):
                textregion = ET.SubElement(page, "TextRegion")
                try:
                    id_indexer = id_indexer
                    id_indexer_l = id_indexer_l
                except:
                    id_indexer = 0
                    id_indexer_l = 0
                textregion.set("id", "r" + str(id_indexer))
                id_indexer += 1

                textregion.set("type", "header")
                # if mm==0:
                #    textregion.set('type','header')
                # else:
                #    textregion.set('type','paragraph')
                coord_text = ET.SubElement(textregion, "Coords")

                points_co = ""
                for lmm in range(len(found_polygons_text_region_h[mm])):

                    if len(found_polygons_text_region_h[mm][lmm]) == 2:
                        points_co = points_co + str(int((found_polygons_text_region_h[mm][lmm][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_text_region_h[mm][lmm][1] + page_coord[0]) / self.scale_y))
                    else:
                        points_co = points_co + str(int((found_polygons_text_region_h[mm][lmm][0][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_text_region_h[mm][lmm][0][1] + page_coord[0]) / self.scale_y))

                    if lmm < (len(found_polygons_text_region_h[mm]) - 1):
                        points_co = points_co + " "
                # print(points_co)
                coord_text.set("points", points_co)

                for j in range(len(all_found_texline_polygons_h[mm])):

                    textline = ET.SubElement(textregion, "TextLine")

                    textline.set("id", "l" + str(id_indexer_l))

                    id_indexer_l += 1

                    coord = ET.SubElement(textline, "Coords")

                    texteq = ET.SubElement(textline, "TextEquiv")

                    uni = ET.SubElement(texteq, "Unicode")
                    uni.text = " "

                    # points = ET.SubElement(coord, 'Points')

                    points_co = ""
                    for l in range(len(all_found_texline_polygons_h[mm][j])):
                        # point = ET.SubElement(coord, 'Point')

                        if not self.curved_line:
                            # point.set('x',str(found_polygons[j][l][0]))
                            # point.set('y',str(found_polygons[j][l][1]))
                            if len(all_found_texline_polygons_h[mm][j][l]) == 2:
                                points_co = points_co + str(int((all_found_texline_polygons_h[mm][j][l][0] + all_box_coord_h[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons_h[mm][j][l][1] + all_box_coord_h[mm][0] + page_coord[0]) / self.scale_y))
                            else:
                                points_co = points_co + str(int((all_found_texline_polygons_h[mm][j][l][0][0] + all_box_coord_h[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons_h[mm][j][l][0][1] + all_box_coord_h[mm][0] + page_coord[0]) / self.scale_y))

                        if self.curved_line:
                            if len(all_found_texline_polygons_h[mm][j][l]) == 2:
                                points_co = points_co + str(int((all_found_texline_polygons_h[mm][j][l][0] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons_h[mm][j][l][1] + page_coord[0]) / self.scale_y))
                            else:
                                points_co = points_co + str(int((all_found_texline_polygons_h[mm][j][l][0][0] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons_h[mm][j][l][0][1] + page_coord[0]) / self.scale_y))

                        if l < (len(all_found_texline_polygons_h[mm][j]) - 1):
                            points_co = points_co + " "
                    # print(points_co)
                    coord.set("points", points_co)

                texteqreg = ET.SubElement(textregion, "TextEquiv")

                unireg = ET.SubElement(texteqreg, "Unicode")
                unireg.text = " "

        if len(found_polygons_drop_capitals) > 0:
            id_indexer = len(contours_h) + len(contours) + len(found_polygons_marginals)
            for mm in range(len(found_polygons_drop_capitals)):
                textregion = ET.SubElement(page, "TextRegion")

                # id_indexer_l=id_indexer_l

                textregion.set("id", "r" + str(id_indexer))
                id_indexer += 1

                textregion.set("type", "drop-capital")
                # if mm==0:
                #    textregion.set('type','header')
                # else:
                #    textregion.set('type','paragraph')
                coord_text = ET.SubElement(textregion, "Coords")

                points_co = ""
                for lmm in range(len(found_polygons_drop_capitals[mm])):

                    if len(found_polygons_drop_capitals[mm][lmm]) == 2:
                        points_co = points_co + str(int((found_polygons_drop_capitals[mm][lmm][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_drop_capitals[mm][lmm][1] + page_coord[0]) / self.scale_y))
                    else:
                        points_co = points_co + str(int((found_polygons_drop_capitals[mm][lmm][0][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_drop_capitals[mm][lmm][0][1] + page_coord[0]) / self.scale_y))

                    if lmm < (len(found_polygons_drop_capitals[mm]) - 1):
                        points_co = points_co + " "
                # print(points_co)
                coord_text.set("points", points_co)

                ##for j in range(len(all_found_texline_polygons_h[mm])):

                ##textline=ET.SubElement(textregion, 'TextLine')

                ##textline.set('id','l'+str(id_indexer_l))

                ##id_indexer_l+=1

                ##coord = ET.SubElement(textline, 'Coords')

                ##texteq=ET.SubElement(textline, 'TextEquiv')

                ##uni=ET.SubElement(texteq, 'Unicode')
                ##uni.text = ' '

                ###points = ET.SubElement(coord, 'Points')

                ##points_co=''
                ##for l in range(len(all_found_texline_polygons_h[mm][j])):
                ###point = ET.SubElement(coord, 'Point')

                ##if not curved_line:
                ###point.set('x',str(found_polygons[j][l][0]))
                ###point.set('y',str(found_polygons[j][l][1]))
                ##if len(all_found_texline_polygons_h[mm][j][l])==2:
                ##points_co=points_co+str( int( (all_found_texline_polygons_h[mm][j][l][0]
                ##+all_box_coord_h[mm][2]+page_coord[2])/self.scale_x) )
                ##points_co=points_co+','
                ##points_co=points_co+str( int( (all_found_texline_polygons_h[mm][j][l][1]
                ##+all_box_coord_h[mm][0]+page_coord[0])/self.scale_y) )
                ##else:
                ##points_co=points_co+str( int( ( all_found_texline_polygons_h[mm][j][l][0][0]
                ##+all_box_coord_h[mm][2]+page_coord[2])/self.scale_x ) )
                ##points_co=points_co+','
                ##points_co=points_co+str( int( ( all_found_texline_polygons_h[mm][j][l][0][1]
                ##+all_box_coord_h[mm][0]+page_coord[0])/self.scale_y) )

                ##if curved_line:
                ##if len(all_found_texline_polygons_h[mm][j][l])==2:
                ##points_co=points_co+str( int( (all_found_texline_polygons_h[mm][j][l][0]
                ##+page_coord[2])/self.scale_x) )
                ##points_co=points_co+','
                ##points_co=points_co+str( int( (all_found_texline_polygons_h[mm][j][l][1]
                ##+page_coord[0])/self.scale_y) )
                ##else:
                ##points_co=points_co+str( int( ( all_found_texline_polygons_h[mm][j][l][0][0]
                ##+page_coord[2])/self.scale_x ) )
                ##points_co=points_co+','
                ##points_co=points_co+str( int( ( all_found_texline_polygons_h[mm][j][l][0][1]
                ##+page_coord[0])/self.scale_y) )

                ##if l<(len(all_found_texline_polygons_h[mm][j])-1):
                ##points_co=points_co+' '
                ###print(points_co)
                ####coord.set('points',points_co)

                texteqreg = ET.SubElement(textregion, "TextEquiv")

                unireg = ET.SubElement(texteqreg, "Unicode")
                unireg.text = " "

        try:

            try:
                ###id_indexer=id_indexer
                id_indexer_l = id_indexer_l
            except:
                ###id_indexer=0
                id_indexer_l = 0
            for mm in range(len(found_polygons_marginals)):
                textregion = ET.SubElement(page, "TextRegion")

                textregion.set("id", id_of_marginalia[mm])

                textregion.set("type", "marginalia")
                # if mm==0:
                #    textregion.set('type','header')
                # else:
                #    textregion.set('type','paragraph')
                coord_text = ET.SubElement(textregion, "Coords")

                points_co = ""
                for lmm in range(len(found_polygons_marginals[mm])):
                    if len(found_polygons_marginals[mm][lmm]) == 2:
                        points_co = points_co + str(int((found_polygons_marginals[mm][lmm][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_marginals[mm][lmm][1] + page_coord[0]) / self.scale_y))
                    else:
                        points_co = points_co + str(int((found_polygons_marginals[mm][lmm][0][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_marginals[mm][lmm][0][1] + page_coord[0]) / self.scale_y))

                    if lmm < (len(found_polygons_marginals[mm]) - 1):
                        points_co = points_co + " "
                # print(points_co)
                coord_text.set("points", points_co)

                for j in range(len(all_found_texline_polygons_marginals[mm])):

                    textline = ET.SubElement(textregion, "TextLine")

                    textline.set("id", "l" + str(id_indexer_l))

                    id_indexer_l += 1

                    coord = ET.SubElement(textline, "Coords")

                    texteq = ET.SubElement(textline, "TextEquiv")

                    uni = ET.SubElement(texteq, "Unicode")
                    uni.text = " "

                    # points = ET.SubElement(coord, 'Points')

                    points_co = ""
                    for l in range(len(all_found_texline_polygons_marginals[mm][j])):
                        # point = ET.SubElement(coord, 'Point')

                        if not self.curved_line:
                            # point.set('x',str(found_polygons[j][l][0]))
                            # point.set('y',str(found_polygons[j][l][1]))
                            if len(all_found_texline_polygons_marginals[mm][j][l]) == 2:
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][0] + all_box_coord_marginals[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][1] + all_box_coord_marginals[mm][0] + page_coord[0]) / self.scale_y))
                            else:
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][0][0] + all_box_coord_marginals[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][0][1] + all_box_coord_marginals[mm][0] + page_coord[0]) / self.scale_y))

                        if self.curved_line:
                            if len(all_found_texline_polygons_marginals[mm][j][l]) == 2:
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][0] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][1] + page_coord[0]) / self.scale_y))
                            else:
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][0][0] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][0][1] + page_coord[0]) / self.scale_y))

                        if l < (len(all_found_texline_polygons_marginals[mm][j]) - 1):
                            points_co = points_co + " "
                    # print(points_co)
                    coord.set("points", points_co)

                texteqreg = ET.SubElement(textregion, "TextEquiv")

                unireg = ET.SubElement(texteqreg, "Unicode")
                unireg.text = " "
        except:
            pass

        try:
            id_indexer = len(contours_h) + len(contours) + len(found_polygons_marginals) + len(found_polygons_drop_capitals)
            for mm in range(len(found_polygons_text_region_img)):
                textregion = ET.SubElement(page, "ImageRegion")

                textregion.set("id", "r" + str(id_indexer))
                id_indexer += 1

                coord_text = ET.SubElement(textregion, "Coords")

                points_co = ""
                for lmm in range(len(found_polygons_text_region_img[mm])):

                    if len(found_polygons_text_region_img[mm][lmm]) == 2:
                        points_co = points_co + str(int((found_polygons_text_region_img[mm][lmm][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_text_region_img[mm][lmm][1] + page_coord[0]) / self.scale_y))
                    else:
                        points_co = points_co + str(int((found_polygons_text_region_img[mm][lmm][0][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_text_region_img[mm][lmm][0][1] + page_coord[0]) / self.scale_y))

                    if lmm < (len(found_polygons_text_region_img[mm]) - 1):
                        points_co = points_co + " "

                coord_text.set("points", points_co)
        except:
            pass

        try:
            for mm in range(len(found_polygons_tables)):
                textregion = ET.SubElement(page, "TableRegion")

                textregion.set("id", "r" + str(id_indexer))
                id_indexer += 1

                coord_text = ET.SubElement(textregion, "Coords")

                points_co = ""
                for lmm in range(len(found_polygons_tables[mm])):

                    if len(found_polygons_tables[mm][lmm]) == 2:
                        points_co = points_co + str(int((found_polygons_tables[mm][lmm][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_tables[mm][lmm][1] + page_coord[0]) / self.scale_y))
                    else:
                        points_co = points_co + str(int((found_polygons_tables[mm][lmm][0][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_tables[mm][lmm][0][1] + page_coord[0]) / self.scale_y))

                    if lmm < (len(found_polygons_tables[mm]) - 1):
                        points_co = points_co + " "

                coord_text.set("points", points_co)
        except:
            pass

        print(dir_of_image)
        print(self.f_name)
        print(os.path.join(dir_of_image, self.f_name) + ".xml")
        tree = ET.ElementTree(data)
        tree.write(os.path.join(dir_of_image, self.f_name) + ".xml")

    def write_into_page_xml(self, contours, page_coord, dir_of_image, order_of_texts, id_of_texts, all_found_texline_polygons, all_box_coord, found_polygons_text_region_img, found_polygons_marginals, all_found_texline_polygons_marginals, all_box_coord_marginals, curved_line, slopes, slopes_marginals):

        found_polygons_text_region = contours
        ##found_polygons_text_region_h=contours_h

        # create the file structure
        data = ET.Element("PcGts")

        data.set("xmlns", "http://schema.primaresearch.org/PAGE/gts/pagecontent/2017-07-15")
        data.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        data.set("xsi:schemaLocation", "http://schema.primaresearch.org/PAGE/gts/pagecontent/2017-07-15")

        metadata = ET.SubElement(data, "Metadata")

        author = ET.SubElement(metadata, "Creator")
        author.text = "SBB_QURATOR"

        created = ET.SubElement(metadata, "Created")
        created.text = "2019-06-17T18:15:12"

        changetime = ET.SubElement(metadata, "LastChange")
        changetime.text = "2019-06-17T18:15:12"

        page = ET.SubElement(data, "Page")

        page.set("imageFilename", self.image_dir)
        page.set("imageHeight", str(self.height_org))
        page.set("imageWidth", str(self.width_org))
        page.set("type", "content")
        page.set("readingDirection", "left-to-right")
        page.set("textLineOrder", "top-to-bottom")

        page_print_sub = ET.SubElement(page, "PrintSpace")
        coord_page = ET.SubElement(page_print_sub, "Coords")
        points_page_print = ""

        for lmm in range(len(self.cont_page[0])):
            if len(self.cont_page[0][lmm]) == 2:
                points_page_print = points_page_print + str(int((self.cont_page[0][lmm][0]) / self.scale_x))
                points_page_print = points_page_print + ","
                points_page_print = points_page_print + str(int((self.cont_page[0][lmm][1]) / self.scale_y))
            else:
                points_page_print = points_page_print + str(int((self.cont_page[0][lmm][0][0]) / self.scale_x))
                points_page_print = points_page_print + ","
                points_page_print = points_page_print + str(int((self.cont_page[0][lmm][0][1]) / self.scale_y))

            if lmm < (len(self.cont_page[0]) - 1):
                points_page_print = points_page_print + " "
        coord_page.set("points", points_page_print)

        if len(contours) > 0:
            region_order = ET.SubElement(page, "ReadingOrder")
            region_order_sub = ET.SubElement(region_order, "OrderedGroup")

            region_order_sub.set("id", "ro357564684568544579089")

            indexer_region = 0

            for vj in order_of_texts:
                name = "coord_text_" + str(vj)
                name = ET.SubElement(region_order_sub, "RegionRefIndexed")

                name.set("index", str(indexer_region))
                name.set("regionRef", id_of_texts[vj])
                indexer_region += 1

            id_of_marginalia = []
            for vm in range(len(found_polygons_marginals)):
                id_of_marginalia.append("r" + str(indexer_region))

                name = "coord_text_" + str(indexer_region)
                name = ET.SubElement(region_order_sub, "RegionRefIndexed")
                name.set("index", str(indexer_region))
                name.set("regionRef", "r" + str(indexer_region))
                indexer_region += 1

            id_indexer = 0
            id_indexer_l = 0

            for mm in range(len(found_polygons_text_region)):
                textregion = ET.SubElement(page, "TextRegion")

                textregion.set("id", "r" + str(id_indexer))
                id_indexer += 1

                textregion.set("type", "paragraph")
                # if mm==0:
                #    textregion.set('type','header')
                # else:
                #    textregion.set('type','paragraph')
                coord_text = ET.SubElement(textregion, "Coords")

                points_co = ""
                for lmm in range(len(found_polygons_text_region[mm])):
                    if len(found_polygons_text_region[mm][lmm]) == 2:
                        points_co = points_co + str(int((found_polygons_text_region[mm][lmm][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_text_region[mm][lmm][1] + page_coord[0]) / self.scale_y))
                    else:
                        points_co = points_co + str(int((found_polygons_text_region[mm][lmm][0][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_text_region[mm][lmm][0][1] + page_coord[0]) / self.scale_y))

                    if lmm < (len(found_polygons_text_region[mm]) - 1):
                        points_co = points_co + " "
                # print(points_co)
                coord_text.set("points", points_co)

                for j in range(len(all_found_texline_polygons[mm])):

                    textline = ET.SubElement(textregion, "TextLine")

                    textline.set("id", "l" + str(id_indexer_l))

                    id_indexer_l += 1

                    coord = ET.SubElement(textline, "Coords")

                    texteq = ET.SubElement(textline, "TextEquiv")

                    uni = ET.SubElement(texteq, "Unicode")
                    uni.text = " "

                    # points = ET.SubElement(coord, 'Points')

                    points_co = ""
                    for l in range(len(all_found_texline_polygons[mm][j])):
                        # point = ET.SubElement(coord, 'Point')

                        if not self.curved_line:
                            # point.set('x',str(found_polygons[j][l][0]))
                            # point.set('y',str(found_polygons[j][l][1]))
                            if len(all_found_texline_polygons[mm][j][l]) == 2:
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0] + all_box_coord[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][1] + all_box_coord[mm][0] + page_coord[0]) / self.scale_y))
                            else:
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0][0] + all_box_coord[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0][1] + all_box_coord[mm][0] + page_coord[0]) / self.scale_y))

                        if (self.curved_line) and abs(slopes[mm]) <= 45:
                            if len(all_found_texline_polygons[mm][j][l]) == 2:
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][1] + page_coord[0]) / self.scale_y))
                            else:
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0][0] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0][1] + page_coord[0]) / self.scale_y))

                        elif (self.curved_line) and abs(slopes[mm]) > 45:
                            if len(all_found_texline_polygons[mm][j][l]) == 2:
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0] + all_box_coord[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][1] + all_box_coord[mm][0] + page_coord[0]) / self.scale_y))
                            else:
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0][0] + all_box_coord[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons[mm][j][l][0][1] + all_box_coord[mm][0] + page_coord[0]) / self.scale_y))

                        if l < (len(all_found_texline_polygons[mm][j]) - 1):
                            points_co = points_co + " "
                    # print(points_co)
                    coord.set("points", points_co)

                texteqreg = ET.SubElement(textregion, "TextEquiv")

                unireg = ET.SubElement(texteqreg, "Unicode")
                unireg.text = " "

        ###print(len(contours_h))
        ###if len(contours_h)>0:
        ###for mm in range(len(found_polygons_text_region_h)):
        ###textregion=ET.SubElement(page, 'TextRegion')
        ###try:
        ###id_indexer=id_indexer
        ###id_indexer_l=id_indexer_l
        ###except:
        ###id_indexer=0
        ###id_indexer_l=0
        ###textregion.set('id','r'+str(id_indexer))
        ###id_indexer+=1

        ###textregion.set('type','header')
        ####if mm==0:
        ####    textregion.set('type','header')
        ####else:
        ####    textregion.set('type','paragraph')
        ###coord_text = ET.SubElement(textregion, 'Coords')

        ###points_co=''
        ###for lmm in range(len(found_polygons_text_region_h[mm])):

        ###if len(found_polygons_text_region_h[mm][lmm])==2:
        ###points_co=points_co+str( int( (found_polygons_text_region_h[mm][lmm][0] +page_coord[2])/self.scale_x ) )
        ###points_co=points_co+','
        ###points_co=points_co+str( int( (found_polygons_text_region_h[mm][lmm][1] +page_coord[0])/self.scale_y ) )
        ###else:
        ###points_co=points_co+str( int((found_polygons_text_region_h[mm][lmm][0][0] +page_coord[2])/self.scale_x) )
        ###points_co=points_co+','
        ###points_co=points_co+str( int((found_polygons_text_region_h[mm][lmm][0][1] +page_coord[0])/self.scale_y) )

        ###if lmm<(len(found_polygons_text_region_h[mm])-1):
        ###points_co=points_co+' '
        ####print(points_co)
        ###coord_text.set('points',points_co)

        ###for j in range(len(all_found_texline_polygons_h[mm])):

        ###textline=ET.SubElement(textregion, 'TextLine')

        ###textline.set('id','l'+str(id_indexer_l))

        ###id_indexer_l+=1

        ###coord = ET.SubElement(textline, 'Coords')

        ###texteq=ET.SubElement(textline, 'TextEquiv')

        ###uni=ET.SubElement(texteq, 'Unicode')
        ###uni.text = ' '

        ####points = ET.SubElement(coord, 'Points')

        ###points_co=''
        ###for l in range(len(all_found_texline_polygons_h[mm][j])):
        ####point = ET.SubElement(coord, 'Point')

        ####point.set('x',str(found_polygons[j][l][0]))
        ####point.set('y',str(found_polygons[j][l][1]))
        ###if len(all_found_texline_polygons_h[mm][j][l])==2:
        ###points_co=points_co+str( int( (all_found_texline_polygons_h[mm][j][l][0] +page_coord[2]
        ###+all_box_coord_h[mm][2])/self.scale_x) )
        ###points_co=points_co+','
        ###points_co=points_co+str( int( (all_found_texline_polygons_h[mm][j][l][1] +page_coord[0]
        ###+all_box_coord_h[mm][0])/self.scale_y) )
        ###else:
        ###points_co=points_co+str( int( ( all_found_texline_polygons_h[mm][j][l][0][0] +page_coord[2]
        ###+all_box_coord_h[mm][2])/self.scale_x ) )
        ###points_co=points_co+','
        ###points_co=points_co+str( int( ( all_found_texline_polygons_h[mm][j][l][0][1] +page_coord[0]
        ###+all_box_coord_h[mm][0])/self.scale_y) )

        ###if l<(len(all_found_texline_polygons_h[mm][j])-1):
        ###points_co=points_co+' '
        ####print(points_co)
        ###coord.set('points',points_co)

        ###texteqreg=ET.SubElement(textregion, 'TextEquiv')

        ###unireg=ET.SubElement(texteqreg, 'Unicode')
        ###unireg.text = ' '
        try:
            # id_indexer_l=0

            try:
                ###id_indexer=id_indexer
                id_indexer_l = id_indexer_l
            except:
                ###id_indexer=0
                id_indexer_l = 0

            for mm in range(len(found_polygons_marginals)):
                textregion = ET.SubElement(page, "TextRegion")

                textregion.set("id", id_of_marginalia[mm])

                textregion.set("type", "marginalia")
                # if mm==0:
                #    textregion.set('type','header')
                # else:
                #    textregion.set('type','paragraph')
                coord_text = ET.SubElement(textregion, "Coords")

                points_co = ""
                for lmm in range(len(found_polygons_marginals[mm])):
                    if len(found_polygons_marginals[mm][lmm]) == 2:
                        points_co = points_co + str(int((found_polygons_marginals[mm][lmm][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_marginals[mm][lmm][1] + page_coord[0]) / self.scale_y))
                    else:
                        points_co = points_co + str(int((found_polygons_marginals[mm][lmm][0][0] + page_coord[2]) / self.scale_x))
                        points_co = points_co + ","
                        points_co = points_co + str(int((found_polygons_marginals[mm][lmm][0][1] + page_coord[0]) / self.scale_y))

                    if lmm < (len(found_polygons_marginals[mm]) - 1):
                        points_co = points_co + " "
                # print(points_co)
                coord_text.set("points", points_co)

                for j in range(len(all_found_texline_polygons_marginals[mm])):

                    textline = ET.SubElement(textregion, "TextLine")

                    textline.set("id", "l" + str(id_indexer_l))

                    id_indexer_l += 1

                    coord = ET.SubElement(textline, "Coords")

                    texteq = ET.SubElement(textline, "TextEquiv")

                    uni = ET.SubElement(texteq, "Unicode")
                    uni.text = " "

                    # points = ET.SubElement(coord, 'Points')

                    points_co = ""
                    for l in range(len(all_found_texline_polygons_marginals[mm][j])):
                        # point = ET.SubElement(coord, 'Point')

                        if not self.curved_line:
                            # point.set('x',str(found_polygons[j][l][0]))
                            # point.set('y',str(found_polygons[j][l][1]))
                            if len(all_found_texline_polygons_marginals[mm][j][l]) == 2:
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][0] + all_box_coord_marginals[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][1] + all_box_coord_marginals[mm][0] + page_coord[0]) / self.scale_y))
                            else:
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][0][0] + all_box_coord_marginals[mm][2] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][0][1] + all_box_coord_marginals[mm][0] + page_coord[0]) / self.scale_y))

                        if self.curved_line:
                            if len(all_found_texline_polygons_marginals[mm][j][l]) == 2:
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][0] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][1] + page_coord[0]) / self.scale_y))
                            else:
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][0][0] + page_coord[2]) / self.scale_x))
                                points_co = points_co + ","
                                points_co = points_co + str(int((all_found_texline_polygons_marginals[mm][j][l][0][1] + page_coord[0]) / self.scale_y))

                        if l < (len(all_found_texline_polygons_marginals[mm][j]) - 1):
                            points_co = points_co + " "
                    # print(points_co)
                    coord.set("points", points_co)
        except:
            pass

        try:

            for mm in range(len(found_polygons_text_region_img)):
                textregion = ET.SubElement(page, "ImageRegion")

                textregion.set("id", "r" + str(id_indexer))
                id_indexer += 1

                coord_text = ET.SubElement(textregion, "Coords")
                points_co = ""
                for lmm in range(len(found_polygons_text_region_img[mm])):
                    points_co = points_co + str(int((found_polygons_text_region_img[mm][lmm, 0, 0] + page_coord[2]) / self.scale_x))
                    points_co = points_co + ","
                    points_co = points_co + str(int((found_polygons_text_region_img[mm][lmm, 0, 1] + page_coord[0]) / self.scale_y))

                    if lmm < (len(found_polygons_text_region_img[mm]) - 1):
                        points_co = points_co + " "

                coord_text.set("points", points_co)
            ###for mm in range(len(found_polygons_text_region_img)):
            ###textregion=ET.SubElement(page, 'ImageRegion')

            ###textregion.set('id','r'+str(id_indexer))
            ###id_indexer+=1

            ###coord_text = ET.SubElement(textregion, 'Coords')
            ###print(found_polygons_text_region_img[mm])
            ###points_co=''
            ###for lmm in range(len(found_polygons_text_region_img[mm])):
            ###print(len(found_polygons_text_region_img[mm][lmm]))

            ###if len(found_polygons_text_region_img[mm][lmm])==2:
            ###points_co=points_co+str( int( (found_polygons_text_region_img[mm][lmm][0]+page_coord[2] )/self.scale_x ) )
            ###points_co=points_co+','
            ###points_co=points_co+str( int( (found_polygons_text_region_img[mm][lmm][1]+page_coord[0] )/self.scale_y ) )
            ###else:
            ###points_co=points_co+str( int((found_polygons_text_region_img[mm][lmm][0][0]+page_coord[2] )/self.scale_x) )
            ###points_co=points_co+','
            ###points_co=points_co+str( int((found_polygons_text_region_img[mm][lmm][0][1]+page_coord[0] )/self.scale_y) )

            ###if lmm<(len(found_polygons_text_region_img[mm])-1):
            ###points_co=points_co+' '

            ###coord_text.set('points',points_co)
        except:
            pass

        ####try:
        ####for mm in range(len(found_polygons_tables)):
        ####textregion=ET.SubElement(page, 'TableRegion')

        ####textregion.set('id','r'+str(id_indexer))
        ####id_indexer+=1

        ####coord_text = ET.SubElement(textregion, 'Coords')

        ####points_co=''
        ####for lmm in range(len(found_polygons_tables[mm])):

        ####if len(found_polygons_tables[mm][lmm])==2:
        ####points_co=points_co+str( int( (found_polygons_tables[mm][lmm][0] +page_coord[2])/self.scale_x ) )
        ####points_co=points_co+','
        ####points_co=points_co+str( int( (found_polygons_tables[mm][lmm][1] +page_coord[0])/self.scale_y ) )
        ####else:
        ####points_co=points_co+str( int((found_polygons_tables[mm][lmm][0][0] +page_coord[2])/self.scale_x) )
        ####points_co=points_co+','
        ####points_co=points_co+str( int((found_polygons_tables[mm][lmm][0][1] +page_coord[0])/self.scale_y) )

        ####if lmm<(len(found_polygons_tables[mm])-1):
        ####points_co=points_co+' '

        ####coord_text.set('points',points_co)
        ####except:
        ####pass
        """

        try:
            for mm in range(len(found_polygons_drop_capitals)):
                textregion=ET.SubElement(page, 'DropCapitals')

                textregion.set('id','r'+str(id_indexer))
                id_indexer+=1


                coord_text = ET.SubElement(textregion, 'Coords')

                points_co=''
                for lmm in range(len(found_polygons_drop_capitals[mm])):

                    if len(found_polygons_drop_capitals[mm][lmm])==2:
                        points_co=points_co+str( int( (found_polygons_drop_capitals[mm][lmm][0] +page_coord[2])/self.scale_x ) )
                        points_co=points_co+','
                        points_co=points_co+str( int( (found_polygons_drop_capitals[mm][lmm][1] +page_coord[0])/self.scale_y ) )
                    else:
                        points_co=points_co+str( int((found_polygons_drop_capitals[mm][lmm][0][0] +page_coord[2])/self.scale_x) )
                        points_co=points_co+','
                        points_co=points_co+str( int((found_polygons_drop_capitals[mm][lmm][0][1] +page_coord[0])/self.scale_y) )

                    if lmm<(len(found_polygons_drop_capitals[mm])-1):
                        points_co=points_co+' '


                coord_text.set('points',points_co)
        except:
            pass
        """

        # print(dir_of_image)
        print(self.f_name)
        # print(os.path.join(dir_of_image, self.f_name) + ".xml")
        tree = ET.ElementTree(data)
        tree.write(os.path.join(dir_of_image, self.f_name) + ".xml")
        # cv2.imwrite(os.path.join(dir_of_image, self.f_name) + ".tif",self.image_org)

    def get_regions_from_xy_2models(self,img,is_image_enhanced):
        img_org=np.copy(img)
        
        img_height_h=img_org.shape[0]
        img_width_h=img_org.shape[1]
        
        model_region, session_region = self.start_new_session_and_model(self.model_region_dir_p_ens)
        
        gaussian_filter=False
        patches=True
        binary=False
        
        
        
        

        ratio_y=1.3
        ratio_x=1
        
        median_blur=False
        
        img= self.resize_image(img_org, int(img_org.shape[0]*ratio_y), int(img_org.shape[1]*ratio_x))
        
        if binary:
            img = self.otsu_copy_binary(img)#self.otsu_copy(img)
            img = img.astype(np.uint16)
            
        if median_blur:
            img=cv2.medianBlur(img,5)
        if gaussian_filter:
            img= cv2.GaussianBlur(img,(5,5),0)
            img = img.astype(np.uint16)
        prediction_regions_org_y=self.do_prediction(patches,img,model_region)
        
        prediction_regions_org_y=self.resize_image(prediction_regions_org_y, img_height_h, img_width_h )
        
        #plt.imshow(prediction_regions_org_y[:,:,0])
        #plt.show()
        #sys.exit()
        prediction_regions_org_y=prediction_regions_org_y[:,:,0]
        
        
        mask_zeros_y=(prediction_regions_org_y[:,:]==0)*1
        
        
        
        
        
        if is_image_enhanced:
            ratio_x=1.2
        else:
            ratio_x=1
            
        ratio_y=1
        median_blur=False
        
        img= self.resize_image(img_org, int(img_org.shape[0]*ratio_y), int(img_org.shape[1]*ratio_x))
        
        if binary:
            img = self.otsu_copy_binary(img)#self.otsu_copy(img)
            img = img.astype(np.uint16)
            
        if median_blur:
            img=cv2.medianBlur(img,5)
        if gaussian_filter:
            img= cv2.GaussianBlur(img,(5,5),0)
            img = img.astype(np.uint16)
        prediction_regions_org=self.do_prediction(patches,img,model_region)
        
        prediction_regions_org=self.resize_image(prediction_regions_org, img_height_h, img_width_h )
        
        ##plt.imshow(prediction_regions_org[:,:,0])
        ##plt.show()
        ##sys.exit()
        prediction_regions_org=prediction_regions_org[:,:,0]
        
        prediction_regions_org[(prediction_regions_org[:,:]==1) & (mask_zeros_y[:,:]==1)]=0
        session_region.close()
        del model_region
        del session_region
        gc.collect()
        ###K.clear_session()
        
        model_region, session_region = self.start_new_session_and_model(self.model_region_dir_p2)
        
        gaussian_filter=False
        patches=True
        binary=False
        
        
        

        ratio_x=1
        ratio_y=1
        median_blur=False
        
        img= self.resize_image(img_org, int(img_org.shape[0]*ratio_y), int(img_org.shape[1]*ratio_x))
        
        if binary:
            img = self.otsu_copy_binary(img)#self.otsu_copy(img)
            img = img.astype(np.uint16)
            
        if median_blur:
            img=cv2.medianBlur(img,5)
        if gaussian_filter:
            img= cv2.GaussianBlur(img,(5,5),0)
            img = img.astype(np.uint16)
            
        marginal_patch=0.2
        prediction_regions_org2=self.do_prediction(patches,img,model_region,marginal_patch)
        
        prediction_regions_org2=self.resize_image(prediction_regions_org2, img_height_h, img_width_h )
        
        #plt.imshow(prediction_regions_org2[:,:,0])
        #plt.show()
        #sys.exit()
        ##prediction_regions_org=prediction_regions_org[:,:,0]
        
        session_region.close()
        del model_region
        del session_region
        gc.collect()
        ###K.clear_session()
        
        mask_zeros2=(prediction_regions_org2[:,:,0]==0)*1
        mask_lines2=(prediction_regions_org2[:,:,0]==3)*1
        
        text_sume_early=( (prediction_regions_org[:,:]==1)*1 ).sum()
        
        
        prediction_regions_org_copy=np.copy(prediction_regions_org)

        
        prediction_regions_org_copy[(prediction_regions_org_copy[:,:]==1) & (mask_zeros2[:,:]==1)]=0
        
        text_sume_second=( (prediction_regions_org_copy[:,:]==1)*1 ).sum()
        
        rate_two_models=text_sume_second/float(text_sume_early)*100
        
        print(rate_two_models,'ratio_of_two_models')
        if is_image_enhanced and rate_two_models<95.50:#98.45:
            pass
        else:
            prediction_regions_org=np.copy(prediction_regions_org_copy)
        
        ##prediction_regions_org[mask_lines2[:,:]==1]=3
        prediction_regions_org[(mask_lines2[:,:]==1) & (prediction_regions_org[:,:]==0)]=3
        
        
        del mask_lines2
        del mask_zeros2
        del prediction_regions_org2
        
        #if is_image_enhanced:
            #pass
        #else:
            #model_region, session_region = self.start_new_session_and_model(self.model_region_dir_p2)
            
            #gaussian_filter=False
            #patches=True
            #binary=False
            
            
            

            #ratio_x=1
            #ratio_y=1
            #median_blur=False
            
            #img= self.resize_image(img_org, int(img_org.shape[0]*ratio_y), int(img_org.shape[1]*ratio_x))
            
            #if binary:
                #img = self.otsu_copy_binary(img)#self.otsu_copy(img)
                #img = img.astype(np.uint16)
                
            #if median_blur:
                #img=cv2.medianBlur(img,5)
            #if gaussian_filter:
                #img= cv2.GaussianBlur(img,(5,5),0)
                #img = img.astype(np.uint16)
            #prediction_regions_org2=self.do_prediction(patches,img,model_region)
            
            #prediction_regions_org2=self.resize_image(prediction_regions_org2, img_height_h, img_width_h )
            
            ##plt.imshow(prediction_regions_org2[:,:,0])
            ##plt.show()
            ##sys.exit()
            ###prediction_regions_org=prediction_regions_org[:,:,0]
            
            #session_region.close()
            #del model_region
            #del session_region
            #gc.collect()
            ####K.clear_session()
            
            #mask_zeros2=(prediction_regions_org2[:,:,0]==0)*1
            #mask_lines2=(prediction_regions_org2[:,:,0]==3)*1
            
            #text_sume_early=( (prediction_regions_org[:,:]==1)*1 ).sum()

            
            #prediction_regions_org[(prediction_regions_org[:,:]==1) & (mask_zeros2[:,:]==1)]=0
            
            ###prediction_regions_org[mask_lines2[:,:]==1]=3
            #prediction_regions_org[(mask_lines2[:,:]==1) & (prediction_regions_org[:,:]==0)]=3
            
            #text_sume_second=( (prediction_regions_org[:,:]==1)*1 ).sum()
            
            #print(text_sume_second/float(text_sume_early)*100,'twomodelsratio')
            
            #del mask_lines2
            #del mask_zeros2
            #del prediction_regions_org2
        
        mask_lines_only=(prediction_regions_org[:,:]==3)*1
        
        prediction_regions_org = cv2.erode(prediction_regions_org[:,:], self.kernel, iterations=2)
        
        #plt.imshow(text_region2_1st_channel)
        #plt.show()
        
        prediction_regions_org = cv2.dilate(prediction_regions_org[:,:], self.kernel, iterations=2)
        
        mask_texts_only=(prediction_regions_org[:,:]==1)*1
        
        mask_images_only=(prediction_regions_org[:,:]==2)*1
        
        
        
        pixel_img=1
        min_area_text=0.00001
        polygons_of_only_texts=self.return_contours_of_interested_region(mask_texts_only,pixel_img,min_area_text)
        
        polygons_of_only_images=self.return_contours_of_interested_region(mask_images_only,pixel_img)
        
        polygons_of_only_lines=self.return_contours_of_interested_region(mask_lines_only,pixel_img,min_area_text)
        
        
        text_regions_p_true=np.zeros(prediction_regions_org.shape)
        #text_regions_p_true[:,:]=text_regions_p_1[:,:]
        
        text_regions_p_true=cv2.fillPoly(text_regions_p_true,pts=polygons_of_only_lines, color=(3,3,3))
        
        ##text_regions_p_true=cv2.fillPoly(text_regions_p_true,pts=polygons_of_only_images, color=(2,2,2))
        text_regions_p_true[:,:][mask_images_only[:,:]==1]=2
        
        text_regions_p_true=cv2.fillPoly(text_regions_p_true,pts=polygons_of_only_texts, color=(1,1,1))
        
        ##print(np.unique(text_regions_p_true))
        
        
        #text_regions_p_true_3d=np.repeat(text_regions_p_1[:, :, np.newaxis], 3, axis=2)
        #text_regions_p_true_3d=text_regions_p_true_3d.astype(np.uint8)
        
        del polygons_of_only_texts
        del polygons_of_only_images
        del polygons_of_only_lines
        del mask_images_only
        del prediction_regions_org
        del img
        del mask_zeros_y
        
        del prediction_regions_org_y
        del img_org
        gc.collect()
        
        return text_regions_p_true
    
    
    def write_images_into_directory(self, img_contoures, dir_of_cropped_imgs, image_page):
        index = 0
        for cont_ind in img_contoures:
            # cont_ind[:,0,0]=cont_ind[:,0,0]/self.scale_x
            # cont_ind[:,0,1]=cont_ind[:,0,1]/self.scale_y

            x, y, w, h = cv2.boundingRect(cont_ind)
            box = [x, y, w, h]
            croped_page, page_coord = crop_image_inside_box(box, image_page)

            croped_page = resize_image(croped_page, int(croped_page.shape[0] / self.scale_y), int(croped_page.shape[1] / self.scale_x))

            path = os.path.join(dir_of_cropped_imgs, self.f_name + "_" + str(index) + ".jpg")
            cv2.imwrite(path, croped_page)
            index += 1

    def get_marginals(self,text_with_lines,text_regions,num_col,slope_deskew):
        mask_marginals=np.zeros((text_with_lines.shape[0],text_with_lines.shape[1]))
        mask_marginals=mask_marginals.astype(np.uint8)
        
        
        text_with_lines=text_with_lines.astype(np.uint8)
        ##text_with_lines=cv2.erode(text_with_lines,self.kernel,iterations=3)
        
        text_with_lines_eroded=cv2.erode(text_with_lines,self.kernel,iterations=5)
        
        if text_with_lines.shape[0]<=1500:
            pass
        elif text_with_lines.shape[0]>1500 and text_with_lines.shape[0]<=1800:
            text_with_lines=self.resize_image(text_with_lines,int(text_with_lines.shape[0]*1.5),text_with_lines.shape[1])
            text_with_lines=cv2.erode(text_with_lines,self.kernel,iterations=5)
            text_with_lines=self.resize_image(text_with_lines,text_with_lines_eroded.shape[0],text_with_lines_eroded.shape[1])
        else:
            text_with_lines=self.resize_image(text_with_lines,int(text_with_lines.shape[0]*1.8),text_with_lines.shape[1])
            text_with_lines=cv2.erode(text_with_lines,self.kernel,iterations=7)
            text_with_lines=self.resize_image(text_with_lines,text_with_lines_eroded.shape[0],text_with_lines_eroded.shape[1])
        

        text_with_lines_y=text_with_lines.sum(axis=0)
        text_with_lines_y_eroded=text_with_lines_eroded.sum(axis=0)
        
        thickness_along_y_percent=text_with_lines_y_eroded.max()/(float(text_with_lines.shape[0]))*100 
        
        #print(thickness_along_y_percent,'thickness_along_y_percent')
        
        if thickness_along_y_percent<30:
            min_textline_thickness=8
        elif thickness_along_y_percent>=30 and thickness_along_y_percent<50:
            min_textline_thickness=20
        else:
            min_textline_thickness=40
        
        
        
        if thickness_along_y_percent>=14:
        
            text_with_lines_y_rev=-1*text_with_lines_y[:]
            #print(text_with_lines_y)
            #print(text_with_lines_y_rev)
            

            
            
            #plt.plot(text_with_lines_y)
            #plt.show()
        
            
            text_with_lines_y_rev=text_with_lines_y_rev-np.min(text_with_lines_y_rev)
            
            #plt.plot(text_with_lines_y_rev)
            #plt.show()
            sigma_gaus=1
            region_sum_0= gaussian_filter1d(text_with_lines_y, sigma_gaus)
            
            region_sum_0_rev=gaussian_filter1d(text_with_lines_y_rev, sigma_gaus)
            
            #plt.plot(region_sum_0_rev)
            #plt.show()
            region_sum_0_updown=region_sum_0[len(region_sum_0)::-1]

            first_nonzero=(next((i for i, x in enumerate(region_sum_0) if x), None))
            last_nonzero=(next((i for i, x in enumerate(region_sum_0_updown) if x), None))


            last_nonzero=len(region_sum_0)-last_nonzero
            
            ##img_sum_0_smooth_rev=-region_sum_0
            
            
            mid_point=(last_nonzero+first_nonzero)/2.
            
            
            one_third_right=(last_nonzero-mid_point)/3.0
            one_third_left=(mid_point-first_nonzero)/3.0
            
            #img_sum_0_smooth_rev=img_sum_0_smooth_rev-np.min(img_sum_0_smooth_rev)
            

            
            
            peaks, _ = find_peaks(text_with_lines_y_rev, height=0)
            

            peaks=np.array(peaks)
            
            
            #print(region_sum_0[peaks])
            ##plt.plot(region_sum_0)
            ##plt.plot(peaks,region_sum_0[peaks],'*')
            ##plt.show()
            #print(first_nonzero,last_nonzero,peaks)
            peaks=peaks[(peaks>first_nonzero) & ((peaks<last_nonzero))]
            
            #print(first_nonzero,last_nonzero,peaks)
            
            
            #print(region_sum_0[peaks]<10)
            ####peaks=peaks[region_sum_0[peaks]<25 ]
            
            #print(region_sum_0[peaks])
            peaks=peaks[region_sum_0[peaks]<min_textline_thickness ]
            #print(peaks)
            #print(first_nonzero,last_nonzero,one_third_right,one_third_left)
            
            if num_col==1:
                peaks_right=peaks[peaks>mid_point]
                peaks_left=peaks[peaks<mid_point]
            if num_col==2:
                peaks_right=peaks[peaks>(mid_point+one_third_right)]
                peaks_left=peaks[peaks<(mid_point-one_third_left)]
                
            
            try:
                point_right=np.min(peaks_right)
            except:
                point_right=last_nonzero
            
            
            try:
                point_left=np.max(peaks_left)
            except:
                point_left=first_nonzero
                
                

                
            #print(point_left,point_right)
            #print(text_regions.shape)
            if point_right>=mask_marginals.shape[1]:
                point_right=mask_marginals.shape[1]-1
                
            try:
                mask_marginals[:,point_left:point_right]=1
            except:
                mask_marginals[:,:]=1
                
            #print(mask_marginals.shape,point_left,point_right,'nadosh')
            mask_marginals_rotated=self.rotate_image(mask_marginals,-slope_deskew)
            
            #print(mask_marginals_rotated.shape,'nadosh')
            mask_marginals_rotated_sum=mask_marginals_rotated.sum(axis=0)
            
            mask_marginals_rotated_sum[mask_marginals_rotated_sum!=0]=1
            index_x=np.array(range(len(mask_marginals_rotated_sum)))+1
            
            index_x_interest=index_x[mask_marginals_rotated_sum==1]
            
            min_point_of_left_marginal=np.min(index_x_interest)-16
            max_point_of_right_marginal=np.max(index_x_interest)+16
            
            if min_point_of_left_marginal<0:
                min_point_of_left_marginal=0
            if max_point_of_right_marginal>=text_regions.shape[1]:
                max_point_of_right_marginal=text_regions.shape[1]-1
            
            
            #print(np.min(index_x_interest) ,np.max(index_x_interest),'minmaxnew')
            #print(mask_marginals_rotated.shape,text_regions.shape,'mask_marginals_rotated')
            #plt.imshow(mask_marginals)
            #plt.show()
            
            #plt.imshow(mask_marginals_rotated)
            #plt.show()

            text_regions[(mask_marginals_rotated[:,:]!=1) & (text_regions[:,:]==1)]=4
            
            #plt.imshow(text_regions)
            #plt.show()
            
            pixel_img=4
            min_area_text=0.00001
            polygons_of_marginals=self.return_contours_of_interested_region(text_regions,pixel_img,min_area_text)
            
            cx_text_only,cy_text_only ,x_min_text_only,x_max_text_only, y_min_text_only ,y_max_text_only,y_cor_x_min_main=self.find_new_features_of_contoures(polygons_of_marginals)
            
            text_regions[(text_regions[:,:]==4)]=1
            
            marginlas_should_be_main_text=[]
            
            x_min_marginals_left=[]
            x_min_marginals_right=[]
            
            for i in range(len(cx_text_only)):
                
                x_width_mar=abs(x_min_text_only[i]-x_max_text_only[i])
                y_height_mar=abs(y_min_text_only[i]-y_max_text_only[i])
                #print(x_width_mar,y_height_mar,y_height_mar/x_width_mar,'y_height_mar')
                if x_width_mar>16 and y_height_mar/x_width_mar<18:
                    marginlas_should_be_main_text.append(polygons_of_marginals[i])
                    if x_min_text_only[i]<(mid_point-one_third_left):
                        x_min_marginals_left_new=x_min_text_only[i]
                        if len(x_min_marginals_left)==0:
                            x_min_marginals_left.append(x_min_marginals_left_new)
                        else:
                            x_min_marginals_left[0]=min(x_min_marginals_left[0],x_min_marginals_left_new)
                    else:
                        x_min_marginals_right_new=x_min_text_only[i]
                        if len(x_min_marginals_right)==0:
                            x_min_marginals_right.append(x_min_marginals_right_new)
                        else:
                            x_min_marginals_right[0]=min(x_min_marginals_right[0],x_min_marginals_right_new)
                            
            if len(x_min_marginals_left)==0:                
                x_min_marginals_left=[0]
            if len(x_min_marginals_right)==0:
                x_min_marginals_right=[text_regions.shape[1]-1]
                    
                        
                        
                        
            #print(x_min_marginals_left[0],x_min_marginals_right[0],'margo')            
                    
            #print(marginlas_should_be_main_text,'marginlas_should_be_main_text')
            text_regions=cv2.fillPoly(text_regions, pts =marginlas_should_be_main_text, color=(4,4))        
            
            #print(np.unique(text_regions))
            
            #text_regions[:,:int(x_min_marginals_left[0])][text_regions[:,:int(x_min_marginals_left[0])]==1]=0
            #text_regions[:,int(x_min_marginals_right[0]):][text_regions[:,int(x_min_marginals_right[0]):]==1]=0
            
            text_regions[:,:int(min_point_of_left_marginal)][text_regions[:,:int(min_point_of_left_marginal)]==1]=0
            text_regions[:,int(max_point_of_right_marginal):][text_regions[:,int(max_point_of_right_marginal):]==1]=0
            
            ###text_regions[:,0:point_left][text_regions[:,0:point_left]==1]=4
            
            ###text_regions[:,point_right:][ text_regions[:,point_right:]==1]=4
            #plt.plot(region_sum_0)
            #plt.plot(peaks,region_sum_0[peaks],'*')
            #plt.show()
            
            
            #plt.imshow(text_regions)
            #plt.show()
            
            #sys.exit()
        else:
            pass
        return text_regions

    def do_order_of_regions(self, contours_only_text_parent, contours_only_text_parent_h, boxes, textline_mask_tot):

        if self.full_layout:
            cx_text_only, cy_text_only, x_min_text_only, _, _, _, y_cor_x_min_main = find_new_features_of_contoures(contours_only_text_parent)
            cx_text_only_h, cy_text_only_h, x_min_text_only_h, _, _, _, y_cor_x_min_main_h = find_new_features_of_contoures(contours_only_text_parent_h)

            try:
                arg_text_con = []
                for ii in range(len(cx_text_only)):
                    for jj in range(len(boxes)):
                        if (x_min_text_only[ii] + 80) >= boxes[jj][0] and (x_min_text_only[ii] + 80) < boxes[jj][1] and y_cor_x_min_main[ii] >= boxes[jj][2] and y_cor_x_min_main[ii] < boxes[jj][3]:
                            arg_text_con.append(jj)
                            break
                arg_arg_text_con = np.argsort(arg_text_con)
                args_contours = np.array(range(len(arg_text_con)))

                arg_text_con_h = []
                for ii in range(len(cx_text_only_h)):
                    for jj in range(len(boxes)):
                        if (x_min_text_only_h[ii] + 80) >= boxes[jj][0] and (x_min_text_only_h[ii] + 80) < boxes[jj][1] and y_cor_x_min_main_h[ii] >= boxes[jj][2] and y_cor_x_min_main_h[ii] < boxes[jj][3]:
                            arg_text_con_h.append(jj)
                            break
                arg_arg_text_con = np.argsort(arg_text_con_h)
                args_contours_h = np.array(range(len(arg_text_con_h)))

                order_by_con_head = np.zeros(len(arg_text_con_h))
                order_by_con_main = np.zeros(len(arg_text_con))

                ref_point = 0
                order_of_texts_tot = []
                id_of_texts_tot = []
                for iij in range(len(boxes)):

                    args_contours_box = args_contours[np.array(arg_text_con) == iij]
                    args_contours_box_h = args_contours_h[np.array(arg_text_con_h) == iij]
                    con_inter_box = []
                    con_inter_box_h = []

                    for i in range(len(args_contours_box)):
                        con_inter_box.append(contours_only_text_parent[args_contours_box[i]])

                    for i in range(len(args_contours_box_h)):
                        con_inter_box_h.append(contours_only_text_parent_h[args_contours_box_h[i]])

                    indexes_sorted, matrix_of_orders, kind_of_texts_sorted, index_by_kind_sorted = order_of_regions(textline_mask_tot[int(boxes[iij][2]) : int(boxes[iij][3]), int(boxes[iij][0]) : int(boxes[iij][1])], con_inter_box, con_inter_box_h, boxes[iij][2])

                    order_of_texts, id_of_texts = order_and_id_of_texts(con_inter_box, con_inter_box_h, matrix_of_orders, indexes_sorted, index_by_kind_sorted, kind_of_texts_sorted, ref_point)

                    indexes_sorted_main = np.array(indexes_sorted)[np.array(kind_of_texts_sorted) == 1]
                    indexes_by_type_main = np.array(index_by_kind_sorted)[np.array(kind_of_texts_sorted) == 1]
                    indexes_sorted_head = np.array(indexes_sorted)[np.array(kind_of_texts_sorted) == 2]
                    indexes_by_type_head = np.array(index_by_kind_sorted)[np.array(kind_of_texts_sorted) == 2]

                    zahler = 0
                    for mtv in args_contours_box:
                        arg_order_v = indexes_sorted_main[zahler]
                        tartib = np.where(indexes_sorted == arg_order_v)[0][0]
                        order_by_con_main[args_contours_box[indexes_by_type_main[zahler]]] = tartib + ref_point
                        zahler = zahler + 1

                    zahler = 0
                    for mtv in args_contours_box_h:
                        arg_order_v = indexes_sorted_head[zahler]
                        tartib = np.where(indexes_sorted == arg_order_v)[0][0]
                        # print(indexes_sorted,np.where(indexes_sorted==arg_order_v ),arg_order_v,tartib,'inshgalla')
                        order_by_con_head[args_contours_box_h[indexes_by_type_head[zahler]]] = tartib + ref_point
                        zahler = zahler + 1

                    for jji in range(len(id_of_texts)):
                        order_of_texts_tot.append(order_of_texts[jji] + ref_point)
                        id_of_texts_tot.append(id_of_texts[jji])
                    ref_point = ref_point + len(id_of_texts)

                order_of_texts_tot = []
                for tj1 in range(len(contours_only_text_parent)):
                    order_of_texts_tot.append(int(order_by_con_main[tj1]))

                for tj1 in range(len(contours_only_text_parent_h)):
                    order_of_texts_tot.append(int(order_by_con_head[tj1]))

                order_text_new = []
                for iii in range(len(order_of_texts_tot)):
                    tartib_new = np.where(np.array(order_of_texts_tot) == iii)[0][0]
                    order_text_new.append(tartib_new)

            except:
                arg_text_con = []
                for ii in range(len(cx_text_only)):
                    for jj in range(len(boxes)):
                        if cx_text_only[ii] >= boxes[jj][0] and cx_text_only[ii] < boxes[jj][1] and cy_text_only[ii] >= boxes[jj][2] and cy_text_only[ii] < boxes[jj][3]:  # this is valid if the center of region identify in which box it is located
                            arg_text_con.append(jj)
                            break
                arg_arg_text_con = np.argsort(arg_text_con)
                args_contours = np.array(range(len(arg_text_con)))

                order_by_con_main = np.zeros(len(arg_text_con))

                ############################# head

                arg_text_con_h = []
                for ii in range(len(cx_text_only_h)):
                    for jj in range(len(boxes)):
                        if cx_text_only_h[ii] >= boxes[jj][0] and cx_text_only_h[ii] < boxes[jj][1] and cy_text_only_h[ii] >= boxes[jj][2] and cy_text_only_h[ii] < boxes[jj][3]:  # this is valid if the center of region identify in which box it is located
                            arg_text_con_h.append(jj)
                            break
                arg_arg_text_con_h = np.argsort(arg_text_con_h)
                args_contours_h = np.array(range(len(arg_text_con_h)))

                order_by_con_head = np.zeros(len(arg_text_con_h))
                #####

                ref_point = 0
                order_of_texts_tot = []
                id_of_texts_tot = []
                for iij in range(len(boxes)):
                    args_contours_box = args_contours[np.array(arg_text_con) == iij]
                    args_contours_box_h = args_contours_h[np.array(arg_text_con_h) == iij]
                    con_inter_box = []
                    con_inter_box_h = []

                    for i in range(len(args_contours_box)):

                        con_inter_box.append(contours_only_text_parent[args_contours_box[i]])
                    for i in range(len(args_contours_box_h)):

                        con_inter_box_h.append(contours_only_text_parent_h[args_contours_box_h[i]])

                    indexes_sorted, matrix_of_orders, kind_of_texts_sorted, index_by_kind_sorted = order_of_regions(textline_mask_tot[int(boxes[iij][2]) : int(boxes[iij][3]), int(boxes[iij][0]) : int(boxes[iij][1])], con_inter_box, con_inter_box_h, boxes[iij][2])

                    order_of_texts, id_of_texts = order_and_id_of_texts(con_inter_box, con_inter_box_h, matrix_of_orders, indexes_sorted, index_by_kind_sorted, kind_of_texts_sorted, ref_point)

                    indexes_sorted_main = np.array(indexes_sorted)[np.array(kind_of_texts_sorted) == 1]
                    indexes_by_type_main = np.array(index_by_kind_sorted)[np.array(kind_of_texts_sorted) == 1]
                    indexes_sorted_head = np.array(indexes_sorted)[np.array(kind_of_texts_sorted) == 2]
                    indexes_by_type_head = np.array(index_by_kind_sorted)[np.array(kind_of_texts_sorted) == 2]

                    zahler = 0
                    for mtv in args_contours_box:
                        arg_order_v = indexes_sorted_main[zahler]
                        tartib = np.where(indexes_sorted == arg_order_v)[0][0]
                        order_by_con_main[args_contours_box[indexes_by_type_main[zahler]]] = tartib + ref_point
                        zahler = zahler + 1

                    zahler = 0
                    for mtv in args_contours_box_h:
                        arg_order_v = indexes_sorted_head[zahler]
                        tartib = np.where(indexes_sorted == arg_order_v)[0][0]
                        # print(indexes_sorted,np.where(indexes_sorted==arg_order_v ),arg_order_v,tartib,'inshgalla')
                        order_by_con_head[args_contours_box_h[indexes_by_type_head[zahler]]] = tartib + ref_point
                        zahler = zahler + 1

                    for jji in range(len(id_of_texts)):
                        order_of_texts_tot.append(order_of_texts[jji] + ref_point)
                        id_of_texts_tot.append(id_of_texts[jji])
                    ref_point = ref_point + len(id_of_texts)

                order_of_texts_tot = []
                for tj1 in range(len(contours_only_text_parent)):
                    order_of_texts_tot.append(int(order_by_con_main[tj1]))

                for tj1 in range(len(contours_only_text_parent_h)):
                    order_of_texts_tot.append(int(order_by_con_head[tj1]))

                order_text_new = []
                for iii in range(len(order_of_texts_tot)):
                    tartib_new = np.where(np.array(order_of_texts_tot) == iii)[0][0]
                    order_text_new.append(tartib_new)
            return order_text_new, id_of_texts_tot

        else:
            cx_text_only, cy_text_only, x_min_text_only, _, _, _, y_cor_x_min_main = find_new_features_of_contoures(contours_only_text_parent)

            try:
                arg_text_con = []
                for ii in range(len(cx_text_only)):
                    for jj in range(len(boxes)):
                        if (x_min_text_only[ii] + 80) >= boxes[jj][0] and (x_min_text_only[ii] + 80) < boxes[jj][1] and y_cor_x_min_main[ii] >= boxes[jj][2] and y_cor_x_min_main[ii] < boxes[jj][3]:
                            arg_text_con.append(jj)
                            break
                arg_arg_text_con = np.argsort(arg_text_con)
                args_contours = np.array(range(len(arg_text_con)))

                order_by_con_main = np.zeros(len(arg_text_con))

                ref_point = 0
                order_of_texts_tot = []
                id_of_texts_tot = []
                for iij in range(len(boxes)):

                    args_contours_box = args_contours[np.array(arg_text_con) == iij]

                    con_inter_box = []
                    con_inter_box_h = []

                    for i in range(len(args_contours_box)):
                        con_inter_box.append(contours_only_text_parent[args_contours_box[i]])

                    indexes_sorted, matrix_of_orders, kind_of_texts_sorted, index_by_kind_sorted = order_of_regions(textline_mask_tot[int(boxes[iij][2]) : int(boxes[iij][3]), int(boxes[iij][0]) : int(boxes[iij][1])], con_inter_box, con_inter_box_h, boxes[iij][2])

                    order_of_texts, id_of_texts = order_and_id_of_texts(con_inter_box, con_inter_box_h, matrix_of_orders, indexes_sorted, index_by_kind_sorted, kind_of_texts_sorted, ref_point)

                    indexes_sorted_main = np.array(indexes_sorted)[np.array(kind_of_texts_sorted) == 1]
                    indexes_by_type_main = np.array(index_by_kind_sorted)[np.array(kind_of_texts_sorted) == 1]
                    indexes_sorted_head = np.array(indexes_sorted)[np.array(kind_of_texts_sorted) == 2]
                    indexes_by_type_head = np.array(index_by_kind_sorted)[np.array(kind_of_texts_sorted) == 2]

                    zahler = 0
                    for mtv in args_contours_box:
                        arg_order_v = indexes_sorted_main[zahler]
                        tartib = np.where(indexes_sorted == arg_order_v)[0][0]
                        order_by_con_main[args_contours_box[indexes_by_type_main[zahler]]] = tartib + ref_point
                        zahler = zahler + 1

                    for jji in range(len(id_of_texts)):
                        order_of_texts_tot.append(order_of_texts[jji] + ref_point)
                        id_of_texts_tot.append(id_of_texts[jji])
                    ref_point = ref_point + len(id_of_texts)

                order_of_texts_tot = []
                for tj1 in range(len(contours_only_text_parent)):
                    order_of_texts_tot.append(int(order_by_con_main[tj1]))

                order_text_new = []
                for iii in range(len(order_of_texts_tot)):
                    tartib_new = np.where(np.array(order_of_texts_tot) == iii)[0][0]
                    order_text_new.append(tartib_new)

            except:
                arg_text_con = []
                for ii in range(len(cx_text_only)):
                    for jj in range(len(boxes)):
                        if cx_text_only[ii] >= boxes[jj][0] and cx_text_only[ii] < boxes[jj][1] and cy_text_only[ii] >= boxes[jj][2] and cy_text_only[ii] < boxes[jj][3]:  # this is valid if the center of region identify in which box it is located
                            arg_text_con.append(jj)
                            break
                arg_arg_text_con = np.argsort(arg_text_con)
                args_contours = np.array(range(len(arg_text_con)))

                order_by_con_main = np.zeros(len(arg_text_con))

                ref_point = 0
                order_of_texts_tot = []
                id_of_texts_tot = []
                for iij in range(len(boxes)):
                    args_contours_box = args_contours[np.array(arg_text_con) == iij]
                    con_inter_box = []
                    con_inter_box_h = []

                    for i in range(len(args_contours_box)):

                        con_inter_box.append(contours_only_text_parent[args_contours_box[i]])

                    indexes_sorted, matrix_of_orders, kind_of_texts_sorted, index_by_kind_sorted = order_of_regions(textline_mask_tot[int(boxes[iij][2]) : int(boxes[iij][3]), int(boxes[iij][0]) : int(boxes[iij][1])], con_inter_box, con_inter_box_h, boxes[iij][2])

                    order_of_texts, id_of_texts = order_and_id_of_texts(con_inter_box, con_inter_box_h, matrix_of_orders, indexes_sorted, index_by_kind_sorted, kind_of_texts_sorted, ref_point)

                    indexes_sorted_main = np.array(indexes_sorted)[np.array(kind_of_texts_sorted) == 1]
                    indexes_by_type_main = np.array(index_by_kind_sorted)[np.array(kind_of_texts_sorted) == 1]
                    indexes_sorted_head = np.array(indexes_sorted)[np.array(kind_of_texts_sorted) == 2]
                    indexes_by_type_head = np.array(index_by_kind_sorted)[np.array(kind_of_texts_sorted) == 2]

                    zahler = 0
                    for mtv in args_contours_box:
                        arg_order_v = indexes_sorted_main[zahler]
                        tartib = np.where(indexes_sorted == arg_order_v)[0][0]
                        order_by_con_main[args_contours_box[indexes_by_type_main[zahler]]] = tartib + ref_point
                        zahler = zahler + 1

                    for jji in range(len(id_of_texts)):
                        order_of_texts_tot.append(order_of_texts[jji] + ref_point)
                        id_of_texts_tot.append(id_of_texts[jji])
                    ref_point = ref_point + len(id_of_texts)

                order_of_texts_tot = []
                for tj1 in range(len(contours_only_text_parent)):
                    order_of_texts_tot.append(int(order_by_con_main[tj1]))

                order_text_new = []
                for iii in range(len(order_of_texts_tot)):
                    tartib_new = np.where(np.array(order_of_texts_tot) == iii)[0][0]
                    order_text_new.append(tartib_new)

            return order_text_new, id_of_texts_tot

    def adhere_drop_capital_region_into_cprresponding_textline(self, text_regions_p, polygons_of_drop_capitals, contours_only_text_parent, contours_only_text_parent_h, all_box_coord, all_box_coord_h, all_found_texline_polygons, all_found_texline_polygons_h):
        # print(np.shape(all_found_texline_polygons),np.shape(all_found_texline_polygons[3]),'all_found_texline_polygonsshape')
        # print(all_found_texline_polygons[3])
        cx_m, cy_m, _, _, _, _, _ = find_new_features_of_contoures(contours_only_text_parent)
        cx_h, cy_h, _, _, _, _, _ = find_new_features_of_contoures(contours_only_text_parent_h)
        cx_d, cy_d, _, _, y_min_d, y_max_d, _ = find_new_features_of_contoures(polygons_of_drop_capitals)

        img_con_all = np.zeros((text_regions_p.shape[0], text_regions_p.shape[1], 3))
        for j_cont in range(len(contours_only_text_parent)):
            img_con_all[all_box_coord[j_cont][0] : all_box_coord[j_cont][1], all_box_coord[j_cont][2] : all_box_coord[j_cont][3], 0] = (j_cont + 1) * 3
            # img_con_all=cv2.fillPoly(img_con_all,pts=[contours_only_text_parent[j_cont]],color=((j_cont+1)*3,(j_cont+1)*3,(j_cont+1)*3))

        # plt.imshow(img_con_all[:,:,0])
        # plt.show()
        # img_con_all=cv2.dilate(img_con_all, self.kernel, iterations=3)

        # plt.imshow(img_con_all[:,:,0])
        # plt.show()
        # print(np.unique(img_con_all[:,:,0]))
        for i_drop in range(len(polygons_of_drop_capitals)):
            # print(i_drop,'i_drop')
            img_con_all_copy = np.copy(img_con_all)
            img_con = np.zeros((text_regions_p.shape[0], text_regions_p.shape[1], 3))
            img_con = cv2.fillPoly(img_con, pts=[polygons_of_drop_capitals[i_drop]], color=(1, 1, 1))

            # plt.imshow(img_con[:,:,0])
            # plt.show()
            ##img_con=cv2.dilate(img_con, self.kernel, iterations=30)

            # plt.imshow(img_con[:,:,0])
            # plt.show()

            # print(np.unique(img_con[:,:,0]))

            img_con_all_copy[:, :, 0] = img_con_all_copy[:, :, 0] + img_con[:, :, 0]

            img_con_all_copy[:, :, 0][img_con_all_copy[:, :, 0] == 1] = 0

            kherej_ghesmat = np.unique(img_con_all_copy[:, :, 0]) / 3
            res_summed_pixels = np.unique(img_con_all_copy[:, :, 0]) % 3
            region_with_intersected_drop = kherej_ghesmat[res_summed_pixels == 1]
            # region_with_intersected_drop=region_with_intersected_drop/3
            region_with_intersected_drop = region_with_intersected_drop.astype(np.uint8)

            # print(len(region_with_intersected_drop),'region_with_intersected_drop1')
            if len(region_with_intersected_drop) == 0:
                img_con_all_copy = np.copy(img_con_all)
                img_con = cv2.dilate(img_con, self.kernel, iterations=4)

                img_con_all_copy[:, :, 0] = img_con_all_copy[:, :, 0] + img_con[:, :, 0]

                img_con_all_copy[:, :, 0][img_con_all_copy[:, :, 0] == 1] = 0

                kherej_ghesmat = np.unique(img_con_all_copy[:, :, 0]) / 3
                res_summed_pixels = np.unique(img_con_all_copy[:, :, 0]) % 3
                region_with_intersected_drop = kherej_ghesmat[res_summed_pixels == 1]
                # region_with_intersected_drop=region_with_intersected_drop/3
                region_with_intersected_drop = region_with_intersected_drop.astype(np.uint8)
            # print(np.unique(img_con_all_copy[:,:,0]))
            if self.curved_line:

                if len(region_with_intersected_drop) > 1:
                    sum_pixels_of_intersection = []
                    for i in range(len(region_with_intersected_drop)):
                        # print((region_with_intersected_drop[i]*3+1))
                        sum_pixels_of_intersection.append(((img_con_all_copy[:, :, 0] == (region_with_intersected_drop[i] * 3 + 1)) * 1).sum())
                    # print(sum_pixels_of_intersection)
                    region_final = region_with_intersected_drop[np.argmax(sum_pixels_of_intersection)] - 1

                    # print(region_final,'region_final')
                    # cx_t,cy_t ,_, _, _ ,_,_= find_new_features_of_contoures(all_found_texline_polygons[int(region_final)])
                    try:
                        cx_t, cy_t, _, _, _, _, _ = find_new_features_of_contoures(all_found_texline_polygons[int(region_final)])
                        # print(all_box_coord[j_cont])
                        # print(cx_t)
                        # print(cy_t)
                        # print(cx_d[i_drop])
                        # print(cy_d[i_drop])
                        y_lines = np.array(cy_t)  # all_box_coord[int(region_final)][0]+np.array(cy_t)

                        # print(y_lines)

                        y_lines[y_lines < y_min_d[i_drop]] = 0
                        # print(y_lines)

                        arg_min = np.argmin(np.abs(y_lines - y_min_d[i_drop]))
                        # print(arg_min)

                        cnt_nearest = np.copy(all_found_texline_polygons[int(region_final)][arg_min])
                        cnt_nearest[:, 0, 0] = all_found_texline_polygons[int(region_final)][arg_min][:, 0, 0]  # +all_box_coord[int(region_final)][2]
                        cnt_nearest[:, 0, 1] = all_found_texline_polygons[int(region_final)][arg_min][:, 0, 1]  # +all_box_coord[int(region_final)][0]

                        img_textlines = np.zeros((text_regions_p.shape[0], text_regions_p.shape[1], 3))
                        img_textlines = cv2.fillPoly(img_textlines, pts=[cnt_nearest], color=(255, 255, 255))
                        img_textlines = cv2.fillPoly(img_textlines, pts=[polygons_of_drop_capitals[i_drop]], color=(255, 255, 255))

                        img_textlines = img_textlines.astype(np.uint8)
                        imgray = cv2.cvtColor(img_textlines, cv2.COLOR_BGR2GRAY)
                        ret, thresh = cv2.threshold(imgray, 0, 255, 0)

                        contours_combined, hierachy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                        # print(len(contours_combined),'len textlines mixed')
                        areas_cnt_text = np.array([cv2.contourArea(contours_combined[j]) for j in range(len(contours_combined))])

                        contours_biggest = contours_combined[np.argmax(areas_cnt_text)]

                        # print(np.shape(contours_biggest))
                        # print(contours_biggest[:])
                        # contours_biggest[:,0,0]=contours_biggest[:,0,0]#-all_box_coord[int(region_final)][2]
                        # contours_biggest[:,0,1]=contours_biggest[:,0,1]#-all_box_coord[int(region_final)][0]

                        # contours_biggest=contours_biggest.reshape(np.shape(contours_biggest)[0],np.shape(contours_biggest)[2])

                        all_found_texline_polygons[int(region_final)][arg_min] = contours_biggest

                    except:
                        # print('gordun1')
                        pass
                elif len(region_with_intersected_drop) == 1:
                    region_final = region_with_intersected_drop[0] - 1

                    # areas_main=np.array([cv2.contourArea(all_found_texline_polygons[int(region_final)][0][j] ) for j in range(len(all_found_texline_polygons[int(region_final)]))])

                    # cx_t,cy_t ,_, _, _ ,_,_= find_new_features_of_contoures(all_found_texline_polygons[int(region_final)])

                    cx_t, cy_t, _, _, _, _, _ = find_new_features_of_contoures(all_found_texline_polygons[int(region_final)])
                    # print(all_box_coord[j_cont])
                    # print(cx_t)
                    # print(cy_t)
                    # print(cx_d[i_drop])
                    # print(cy_d[i_drop])
                    y_lines = np.array(cy_t)  # all_box_coord[int(region_final)][0]+np.array(cy_t)

                    y_lines[y_lines < y_min_d[i_drop]] = 0
                    # print(y_lines)

                    arg_min = np.argmin(np.abs(y_lines - y_min_d[i_drop]))
                    # print(arg_min)

                    cnt_nearest = np.copy(all_found_texline_polygons[int(region_final)][arg_min])
                    cnt_nearest[:, 0, 0] = all_found_texline_polygons[int(region_final)][arg_min][:, 0, 0]  # +all_box_coord[int(region_final)][2]
                    cnt_nearest[:, 0, 1] = all_found_texline_polygons[int(region_final)][arg_min][:, 0, 1]  # +all_box_coord[int(region_final)][0]

                    img_textlines = np.zeros((text_regions_p.shape[0], text_regions_p.shape[1], 3))
                    img_textlines = cv2.fillPoly(img_textlines, pts=[cnt_nearest], color=(255, 255, 255))
                    img_textlines = cv2.fillPoly(img_textlines, pts=[polygons_of_drop_capitals[i_drop]], color=(255, 255, 255))

                    img_textlines = img_textlines.astype(np.uint8)

                    # plt.imshow(img_textlines)
                    # plt.show()
                    imgray = cv2.cvtColor(img_textlines, cv2.COLOR_BGR2GRAY)
                    ret, thresh = cv2.threshold(imgray, 0, 255, 0)

                    contours_combined, hierachy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                    # print(len(contours_combined),'len textlines mixed')
                    areas_cnt_text = np.array([cv2.contourArea(contours_combined[j]) for j in range(len(contours_combined))])

                    contours_biggest = contours_combined[np.argmax(areas_cnt_text)]

                    # print(np.shape(contours_biggest))
                    # print(contours_biggest[:])
                    # contours_biggest[:,0,0]=contours_biggest[:,0,0]#-all_box_coord[int(region_final)][2]
                    # contours_biggest[:,0,1]=contours_biggest[:,0,1]#-all_box_coord[int(region_final)][0]
                    # print(np.shape(contours_biggest),'contours_biggest')
                    # print(np.shape(all_found_texline_polygons[int(region_final)][arg_min]))
                    ##contours_biggest=contours_biggest.reshape(np.shape(contours_biggest)[0],np.shape(contours_biggest)[2])
                    all_found_texline_polygons[int(region_final)][arg_min] = contours_biggest

                    # print(cx_t,'print')
                    try:
                        # print(all_found_texline_polygons[j_cont][0])
                        cx_t, cy_t, _, _, _, _, _ = find_new_features_of_contoures(all_found_texline_polygons[int(region_final)])
                        # print(all_box_coord[j_cont])
                        # print(cx_t)
                        # print(cy_t)
                        # print(cx_d[i_drop])
                        # print(cy_d[i_drop])
                        y_lines = all_box_coord[int(region_final)][0] + np.array(cy_t)

                        y_lines[y_lines < y_min_d[i_drop]] = 0
                        # print(y_lines)

                        arg_min = np.argmin(np.abs(y_lines - y_min_d[i_drop]))
                        # print(arg_min)

                        cnt_nearest = np.copy(all_found_texline_polygons[int(region_final)][arg_min])
                        cnt_nearest[:, 0, 0] = all_found_texline_polygons[int(region_final)][arg_min][:, 0, 0]  # +all_box_coord[int(region_final)][2]
                        cnt_nearest[:, 0, 1] = all_found_texline_polygons[int(region_final)][arg_min][:, 0, 1]  # +all_box_coord[int(region_final)][0]

                        img_textlines = np.zeros((text_regions_p.shape[0], text_regions_p.shape[1], 3))
                        img_textlines = cv2.fillPoly(img_textlines, pts=[cnt_nearest], color=(255, 255, 255))
                        img_textlines = cv2.fillPoly(img_textlines, pts=[polygons_of_drop_capitals[i_drop]], color=(255, 255, 255))

                        img_textlines = img_textlines.astype(np.uint8)
                        imgray = cv2.cvtColor(img_textlines, cv2.COLOR_BGR2GRAY)
                        ret, thresh = cv2.threshold(imgray, 0, 255, 0)

                        contours_combined, hierachy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                        # print(len(contours_combined),'len textlines mixed')
                        areas_cnt_text = np.array([cv2.contourArea(contours_combined[j]) for j in range(len(contours_combined))])

                        contours_biggest = contours_combined[np.argmax(areas_cnt_text)]

                        # print(np.shape(contours_biggest))
                        # print(contours_biggest[:])
                        contours_biggest[:, 0, 0] = contours_biggest[:, 0, 0]  # -all_box_coord[int(region_final)][2]
                        contours_biggest[:, 0, 1] = contours_biggest[:, 0, 1]  # -all_box_coord[int(region_final)][0]

                        ##contours_biggest=contours_biggest.reshape(np.shape(contours_biggest)[0],np.shape(contours_biggest)[2])
                        all_found_texline_polygons[int(region_final)][arg_min] = contours_biggest
                        # all_found_texline_polygons[int(region_final)][arg_min]=contours_biggest

                    except:
                        pass
                else:
                    pass

                ##cx_t,cy_t ,_, _, _ ,_,_= find_new_features_of_contoures(all_found_texline_polygons[int(region_final)])
                ###print(all_box_coord[j_cont])
                ###print(cx_t)
                ###print(cy_t)
                ###print(cx_d[i_drop])
                ###print(cy_d[i_drop])
                ##y_lines=all_box_coord[int(region_final)][0]+np.array(cy_t)

                ##y_lines[y_lines<y_min_d[i_drop]]=0
                ###print(y_lines)

                ##arg_min=np.argmin(np.abs(y_lines-y_min_d[i_drop])  )
                ###print(arg_min)

                ##cnt_nearest=np.copy(all_found_texline_polygons[int(region_final)][arg_min])
                ##cnt_nearest[:,0,0]=all_found_texline_polygons[int(region_final)][arg_min][:,0,0]#+all_box_coord[int(region_final)][2]
                ##cnt_nearest[:,0,1]=all_found_texline_polygons[int(region_final)][arg_min][:,0,1]#+all_box_coord[int(region_final)][0]

                ##img_textlines=np.zeros((text_regions_p.shape[0],text_regions_p.shape[1],3))
                ##img_textlines=cv2.fillPoly(img_textlines,pts=[cnt_nearest],color=(255,255,255))
                ##img_textlines=cv2.fillPoly(img_textlines,pts=[polygons_of_drop_capitals[i_drop] ],color=(255,255,255))

                ##img_textlines=img_textlines.astype(np.uint8)

                ##plt.imshow(img_textlines)
                ##plt.show()
                ##imgray = cv2.cvtColor(img_textlines, cv2.COLOR_BGR2GRAY)
                ##ret, thresh = cv2.threshold(imgray, 0, 255, 0)

                ##contours_combined,hierachy=cv2.findContours(thresh,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)

                ##print(len(contours_combined),'len textlines mixed')
                ##areas_cnt_text=np.array([cv2.contourArea(contours_combined[j]) for j in range(len(contours_combined))])

                ##contours_biggest=contours_combined[np.argmax(areas_cnt_text)]

                ###print(np.shape(contours_biggest))
                ###print(contours_biggest[:])
                ##contours_biggest[:,0,0]=contours_biggest[:,0,0]#-all_box_coord[int(region_final)][2]
                ##contours_biggest[:,0,1]=contours_biggest[:,0,1]#-all_box_coord[int(region_final)][0]

                ##contours_biggest=contours_biggest.reshape(np.shape(contours_biggest)[0],np.shape(contours_biggest)[2])
                ##all_found_texline_polygons[int(region_final)][arg_min]=contours_biggest

            else:
                if len(region_with_intersected_drop) > 1:
                    sum_pixels_of_intersection = []
                    for i in range(len(region_with_intersected_drop)):
                        # print((region_with_intersected_drop[i]*3+1))
                        sum_pixels_of_intersection.append(((img_con_all_copy[:, :, 0] == (region_with_intersected_drop[i] * 3 + 1)) * 1).sum())
                    # print(sum_pixels_of_intersection)
                    region_final = region_with_intersected_drop[np.argmax(sum_pixels_of_intersection)] - 1

                    # print(region_final,'region_final')
                    # cx_t,cy_t ,_, _, _ ,_,_= find_new_features_of_contoures(all_found_texline_polygons[int(region_final)])
                    try:
                        cx_t, cy_t, _, _, _, _, _ = find_new_features_of_contoures(all_found_texline_polygons[int(region_final)])
                        # print(all_box_coord[j_cont])
                        # print(cx_t)
                        # print(cy_t)
                        # print(cx_d[i_drop])
                        # print(cy_d[i_drop])
                        y_lines = all_box_coord[int(region_final)][0] + np.array(cy_t)

                        # print(y_lines)

                        y_lines[y_lines < y_min_d[i_drop]] = 0
                        # print(y_lines)

                        arg_min = np.argmin(np.abs(y_lines - y_min_d[i_drop]))
                        # print(arg_min)

                        cnt_nearest = np.copy(all_found_texline_polygons[int(region_final)][arg_min])
                        cnt_nearest[:, 0] = all_found_texline_polygons[int(region_final)][arg_min][:, 0] + all_box_coord[int(region_final)][2]
                        cnt_nearest[:, 1] = all_found_texline_polygons[int(region_final)][arg_min][:, 1] + all_box_coord[int(region_final)][0]

                        img_textlines = np.zeros((text_regions_p.shape[0], text_regions_p.shape[1], 3))
                        img_textlines = cv2.fillPoly(img_textlines, pts=[cnt_nearest], color=(255, 255, 255))
                        img_textlines = cv2.fillPoly(img_textlines, pts=[polygons_of_drop_capitals[i_drop]], color=(255, 255, 255))

                        img_textlines = img_textlines.astype(np.uint8)
                        imgray = cv2.cvtColor(img_textlines, cv2.COLOR_BGR2GRAY)
                        ret, thresh = cv2.threshold(imgray, 0, 255, 0)

                        contours_combined, hierachy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                        # print(len(contours_combined),'len textlines mixed')
                        areas_cnt_text = np.array([cv2.contourArea(contours_combined[j]) for j in range(len(contours_combined))])

                        contours_biggest = contours_combined[np.argmax(areas_cnt_text)]

                        # print(np.shape(contours_biggest))
                        # print(contours_biggest[:])
                        contours_biggest[:, 0, 0] = contours_biggest[:, 0, 0] - all_box_coord[int(region_final)][2]
                        contours_biggest[:, 0, 1] = contours_biggest[:, 0, 1] - all_box_coord[int(region_final)][0]

                        contours_biggest = contours_biggest.reshape(np.shape(contours_biggest)[0], np.shape(contours_biggest)[2])

                        all_found_texline_polygons[int(region_final)][arg_min] = contours_biggest

                    except:
                        # print('gordun1')
                        pass
                elif len(region_with_intersected_drop) == 1:
                    region_final = region_with_intersected_drop[0] - 1

                    # areas_main=np.array([cv2.contourArea(all_found_texline_polygons[int(region_final)][0][j] ) for j in range(len(all_found_texline_polygons[int(region_final)]))])

                    # cx_t,cy_t ,_, _, _ ,_,_= find_new_features_of_contoures(all_found_texline_polygons[int(region_final)])

                    # print(cx_t,'print')
                    try:
                        # print(all_found_texline_polygons[j_cont][0])
                        cx_t, cy_t, _, _, _, _, _ = find_new_features_of_contoures(all_found_texline_polygons[int(region_final)])
                        # print(all_box_coord[j_cont])
                        # print(cx_t)
                        # print(cy_t)
                        # print(cx_d[i_drop])
                        # print(cy_d[i_drop])
                        y_lines = all_box_coord[int(region_final)][0] + np.array(cy_t)

                        y_lines[y_lines < y_min_d[i_drop]] = 0
                        # print(y_lines)

                        arg_min = np.argmin(np.abs(y_lines - y_min_d[i_drop]))
                        # print(arg_min)

                        cnt_nearest = np.copy(all_found_texline_polygons[int(region_final)][arg_min])
                        cnt_nearest[:, 0] = all_found_texline_polygons[int(region_final)][arg_min][:, 0] + all_box_coord[int(region_final)][2]
                        cnt_nearest[:, 1] = all_found_texline_polygons[int(region_final)][arg_min][:, 1] + all_box_coord[int(region_final)][0]

                        img_textlines = np.zeros((text_regions_p.shape[0], text_regions_p.shape[1], 3))
                        img_textlines = cv2.fillPoly(img_textlines, pts=[cnt_nearest], color=(255, 255, 255))
                        img_textlines = cv2.fillPoly(img_textlines, pts=[polygons_of_drop_capitals[i_drop]], color=(255, 255, 255))

                        img_textlines = img_textlines.astype(np.uint8)
                        imgray = cv2.cvtColor(img_textlines, cv2.COLOR_BGR2GRAY)
                        ret, thresh = cv2.threshold(imgray, 0, 255, 0)

                        contours_combined, hierachy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                        # print(len(contours_combined),'len textlines mixed')
                        areas_cnt_text = np.array([cv2.contourArea(contours_combined[j]) for j in range(len(contours_combined))])

                        contours_biggest = contours_combined[np.argmax(areas_cnt_text)]

                        # print(np.shape(contours_biggest))
                        # print(contours_biggest[:])
                        contours_biggest[:, 0, 0] = contours_biggest[:, 0, 0] - all_box_coord[int(region_final)][2]
                        contours_biggest[:, 0, 1] = contours_biggest[:, 0, 1] - all_box_coord[int(region_final)][0]

                        contours_biggest = contours_biggest.reshape(np.shape(contours_biggest)[0], np.shape(contours_biggest)[2])
                        all_found_texline_polygons[int(region_final)][arg_min] = contours_biggest
                        # all_found_texline_polygons[int(region_final)][arg_min]=contours_biggest

                    except:
                        pass
                else:
                    pass

        #####for i_drop in range(len(polygons_of_drop_capitals)):
        #####for j_cont in range(len(contours_only_text_parent)):
        #####img_con=np.zeros((text_regions_p.shape[0],text_regions_p.shape[1],3))
        #####img_con=cv2.fillPoly(img_con,pts=[polygons_of_drop_capitals[i_drop] ],color=(255,255,255))
        #####img_con=cv2.fillPoly(img_con,pts=[contours_only_text_parent[j_cont]],color=(255,255,255))

        #####img_con=img_con.astype(np.uint8)
        ######imgray = cv2.cvtColor(img_con, cv2.COLOR_BGR2GRAY)
        ######ret, thresh = cv2.threshold(imgray, 0, 255, 0)

        ######contours_new,hierachy=cv2.findContours(thresh,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)

        #####contours_new,hir_new=return_contours_of_image(img_con)
        #####contours_new_parent=return_parent_contours( contours_new,hir_new)
        ######plt.imshow(img_con)
        ######plt.show()
        #####try:
        #####if len(contours_new_parent)==1:
        ######print(all_found_texline_polygons[j_cont][0])
        #####cx_t,cy_t ,_, _, _ ,_,_= find_new_features_of_contoures(all_found_texline_polygons[j_cont])
        ######print(all_box_coord[j_cont])
        ######print(cx_t)
        ######print(cy_t)
        ######print(cx_d[i_drop])
        ######print(cy_d[i_drop])
        #####y_lines=all_box_coord[j_cont][0]+np.array(cy_t)

        ######print(y_lines)

        #####arg_min=np.argmin(np.abs(y_lines-y_min_d[i_drop])  )
        ######print(arg_min)

        #####cnt_nearest=np.copy(all_found_texline_polygons[j_cont][arg_min])
        #####cnt_nearest[:,0]=all_found_texline_polygons[j_cont][arg_min][:,0]+all_box_coord[j_cont][2]
        #####cnt_nearest[:,1]=all_found_texline_polygons[j_cont][arg_min][:,1]+all_box_coord[j_cont][0]

        #####img_textlines=np.zeros((text_regions_p.shape[0],text_regions_p.shape[1],3))
        #####img_textlines=cv2.fillPoly(img_textlines,pts=[cnt_nearest],color=(255,255,255))
        #####img_textlines=cv2.fillPoly(img_textlines,pts=[polygons_of_drop_capitals[i_drop] ],color=(255,255,255))

        #####img_textlines=img_textlines.astype(np.uint8)
        #####imgray = cv2.cvtColor(img_textlines, cv2.COLOR_BGR2GRAY)
        #####ret, thresh = cv2.threshold(imgray, 0, 255, 0)

        #####contours_combined,hierachy=cv2.findContours(thresh,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)

        #####areas_cnt_text=np.array([cv2.contourArea(contours_combined[j]) for j in range(len(contours_combined))])

        #####contours_biggest=contours_combined[np.argmax(areas_cnt_text)]

        ######print(np.shape(contours_biggest))
        ######print(contours_biggest[:])
        #####contours_biggest[:,0,0]=contours_biggest[:,0,0]-all_box_coord[j_cont][2]
        #####contours_biggest[:,0,1]=contours_biggest[:,0,1]-all_box_coord[j_cont][0]

        #####all_found_texline_polygons[j_cont][arg_min]=contours_biggest
        ######print(contours_biggest)
        ######plt.imshow(img_textlines[:,:,0])
        ######plt.show()
        #####else:
        #####pass
        #####except:
        #####pass
        return all_found_texline_polygons

    def save_plot_of_layout_main(self, text_regions_p, image_page):
        values = np.unique(text_regions_p[:, :])

        # pixels=['Background' , 'Main text' , 'Heading' , 'Marginalia' ,'Drop capitals' , 'Images' , 'Seperators' , 'Tables', 'Graphics']

        pixels = ["Background", "Main text", "Images", "Seperators", "Marginalia"]
        values_indexes = [0, 1, 2, 3, 4]
        plt.figure(figsize=(40, 40))
        plt.rcParams["font.size"] = "40"

        im = plt.imshow(text_regions_p[:, :])
        colors = [im.cmap(im.norm(value)) for value in values]
        patches = [mpatches.Patch(color=colors[np.where(values == i)[0][0]], label="{l}".format(l=pixels[int(np.where(values_indexes == i)[0][0])])) for i in values]
        plt.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.0, fontsize=40)
        plt.savefig(os.path.join(self.dir_of_layout, self.f_name + "_layout_main.png"))

    def save_plot_of_layout_main_all(self, text_regions_p, image_page):
        values = np.unique(text_regions_p[:, :])

        # pixels=['Background' , 'Main text' , 'Heading' , 'Marginalia' ,'Drop capitals' , 'Images' , 'Seperators' , 'Tables', 'Graphics']

        pixels = ["Background", "Main text", "Images", "Seperators", "Marginalia"]
        values_indexes = [0, 1, 2, 3, 4]

        plt.figure(figsize=(70, 40))
        plt.rcParams["font.size"] = "40"
        plt.subplot(1, 2, 1)
        plt.imshow(image_page)
        plt.subplot(1, 2, 2)
        im = plt.imshow(text_regions_p[:, :])
        colors = [im.cmap(im.norm(value)) for value in values]
        patches = [mpatches.Patch(color=colors[np.where(values == i)[0][0]], label="{l}".format(l=pixels[int(np.where(values_indexes == i)[0][0])])) for i in values]
        plt.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.0, fontsize=60)

        plt.savefig(os.path.join(self.dir_of_all, self.f_name + "_layout_main_and_page.png"))

    def save_plot_of_layout(self, text_regions_p, image_page):
        values = np.unique(text_regions_p[:, :])

        # pixels=['Background' , 'Main text' , 'Heading' , 'Marginalia' ,'Drop capitals' , 'Images' , 'Seperators' , 'Tables', 'Graphics']

        pixels = ["Background", "Main text", "Header", "Marginalia", "Drop capitals", "Images", "Seperators"]
        values_indexes = [0, 1, 2, 8, 4, 5, 6]
        plt.figure(figsize=(40, 40))
        plt.rcParams["font.size"] = "40"
        im = plt.imshow(text_regions_p[:, :])
        colors = [im.cmap(im.norm(value)) for value in values]
        patches = [mpatches.Patch(color=colors[np.where(values == i)[0][0]], label="{l}".format(l=pixels[int(np.where(values_indexes == i)[0][0])])) for i in values]
        plt.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.0, fontsize=40)
        plt.savefig(os.path.join(self.dir_of_layout, self.f_name + "_layout.png"))

    def save_plot_of_layout_all(self, text_regions_p, image_page):
        values = np.unique(text_regions_p[:, :])

        # pixels=['Background' , 'Main text' , 'Heading' , 'Marginalia' ,'Drop capitals' , 'Images' , 'Seperators' , 'Tables', 'Graphics']

        pixels = ["Background", "Main text", "Header", "Marginalia", "Drop capitals", "Images", "Seperators"]
        values_indexes = [0, 1, 2, 8, 4, 5, 6]

        plt.figure(figsize=(70, 40))
        plt.rcParams["font.size"] = "40"
        plt.subplot(1, 2, 1)
        plt.imshow(image_page)
        plt.subplot(1, 2, 2)
        im = plt.imshow(text_regions_p[:, :])
        colors = [im.cmap(im.norm(value)) for value in values]
        patches = [mpatches.Patch(color=colors[np.where(values == i)[0][0]], label="{l}".format(l=pixels[int(np.where(values_indexes == i)[0][0])])) for i in values]
        plt.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.0, fontsize=60)

        plt.savefig(os.path.join(self.dir_of_all, self.f_name + "_layout_and_page.png"))

    def save_deskewed_image(self, slope_deskew):
        img_rotated = self.rotyate_image_different(self.image_org, slope_deskew)

        if self.dir_of_all is not None:
            cv2.imwrite(os.path.join(self.dir_of_all, self.f_name + "_org.png"), self.image_org)

        cv2.imwrite(os.path.join(self.dir_of_deskewed, self.f_name + "_deskewed.png"), img_rotated)
        del img_rotated

    def run(self):
        is_image_enhanced = False
        # get image and sclaes, then extract the page of scanned image
        t1 = time.time()

        ##########

        ###is_image_enhanced,img_org,img_res=self.resize_and_enhance_image(is_image_enhanced)
        is_image_enhanced, img_org, img_res, num_col_classifier, num_column_is_classified = self.resize_and_enhance_image_with_column_classifier(is_image_enhanced)

        print(is_image_enhanced, "is_image_enhanced")
        K.clear_session()
        scale = 1
        if (self.allow_enhancement) and is_image_enhanced:
            cv2.imwrite(os.path.join(self.dir_out, self.f_name) + ".tif", img_res)
            img_res = img_res.astype(np.uint8)
            self.get_image_and_scales(img_org, img_res, scale)

        if (not self.allow_enhancement) and is_image_enhanced:
            self.get_image_and_scales_after_enhancing(img_org, img_res)

        if (self.allow_enhancement) and not is_image_enhanced:
            self.get_image_and_scales(img_org, img_res, scale)

        if (not self.allow_enhancement) and not is_image_enhanced:
            self.get_image_and_scales(img_org, img_res, scale)

        if (self.allow_scaling) and not is_image_enhanced:
            img_org, img_res, is_image_enhanced = self.resize_image_with_column_classifier(is_image_enhanced)
            self.get_image_and_scales_after_enhancing(img_org, img_res)

        # print(self.scale_x)

        print("enhancing: " + str(time.time() - t1))
        text_regions_p_1 = self.get_regions_from_xy_2models(img_res, is_image_enhanced)
        K.clear_session()
        gc.collect()

        print("textregion: " + str(time.time() - t1))

        img_g = cv2.imread(self.image_dir, 0)
        img_g = img_g.astype(np.uint8)

        img_g3 = np.zeros((img_g.shape[0], img_g.shape[1], 3))

        img_g3 = img_g3.astype(np.uint8)

        img_g3[:, :, 0] = img_g[:, :]
        img_g3[:, :, 1] = img_g[:, :]
        img_g3[:, :, 2] = img_g[:, :]

        ###self.produce_groundtruth_for_textline()
        image_page, page_coord = self.extract_page()

        # print(image_page.shape,'page')

        if self.dir_of_all is not None:
            cv2.imwrite(os.path.join(self.dir_of_all, self.f_name + "_page.png"), image_page)
        ##########
        K.clear_session()
        gc.collect()

        img_g3_page = img_g3[page_coord[0] : page_coord[1], page_coord[2] : page_coord[3], :]
        del img_g3
        del img_g

        text_regions_p_1 = text_regions_p_1[page_coord[0] : page_coord[1], page_coord[2] : page_coord[3]]

        mask_images = (text_regions_p_1[:, :] == 2) * 1
        mask_lines = (text_regions_p_1[:, :] == 3) * 1

        mask_images = mask_images.astype(np.uint8)
        mask_lines = mask_lines.astype(np.uint8)

        mask_images = cv2.erode(mask_images[:, :], self.kernel, iterations=10)

        img_only_regions_with_sep = ((text_regions_p_1[:, :] != 3) & (text_regions_p_1[:, :] != 0)) * 1
        img_only_regions_with_sep = img_only_regions_with_sep.astype(np.uint8)
        img_only_regions = cv2.erode(img_only_regions_with_sep[:, :], self.kernel, iterations=6)

        try:
            num_col, peaks_neg_fin = find_num_col(img_only_regions, multiplier=6.0)
            if not num_column_is_classified:
                num_col_classifier = num_col + 1
        except:
            num_col = None
            peaks_neg_fin = []

        #print(num_col, "num_colnum_col")
        if num_col is None:
            txt_con_org = []
            order_text_new = []
            id_of_texts_tot = []
            all_found_texline_polygons = []
            all_box_coord = []
            polygons_of_images = []
            polygons_of_marginals = []
            all_found_texline_polygons_marginals = []
            all_box_coord_marginals = []
            slopes = []
            slopes_marginals = []
            self.write_into_page_xml(txt_con_org, page_coord, self.dir_out, order_text_new, id_of_texts_tot, all_found_texline_polygons, all_box_coord, polygons_of_images, polygons_of_marginals, all_found_texline_polygons_marginals, all_box_coord_marginals, self.curved_line, slopes, slopes_marginals)
        else:
            # pass
            try:
                patches = True
                scaler_h_textline = 1  # 1.2#1.2
                scaler_w_textline = 1  # 0.9#1
                textline_mask_tot_ea, textline_mask_tot_long_shot = self.textline_contours(image_page, patches, scaler_h_textline, scaler_w_textline)

                K.clear_session()
                gc.collect()

                #print(np.unique(textline_mask_tot_ea[:, :]), "textline")

                if self.dir_of_all is not None:

                    values = np.unique(textline_mask_tot_ea[:, :])
                    pixels = ["Background", "Textlines"]
                    values_indexes = [0, 1]
                    plt.figure(figsize=(70, 40))
                    plt.rcParams["font.size"] = "40"
                    plt.subplot(1, 2, 1)
                    plt.imshow(image_page)
                    plt.subplot(1, 2, 2)
                    im = plt.imshow(textline_mask_tot_ea[:, :])
                    colors = [im.cmap(im.norm(value)) for value in values]
                    patches = [mpatches.Patch(color=colors[np.where(values == i)[0][0]], label="{l}".format(l=pixels[int(np.where(values_indexes == i)[0][0])])) for i in values]
                    plt.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.0, fontsize=60)

                    plt.savefig(os.path.join(self.dir_of_all, self.f_name + "_textline_and_page.png"))
                print("textline: " + str(time.time() - t1))
                # plt.imshow(textline_mask_tot_ea)
                # plt.show()
                # sys.exit()

                sigma = 2
                main_page_deskew = True
                slope_deskew = return_deskew_slop(cv2.erode(textline_mask_tot_ea, self.kernel, iterations=2), sigma, main_page_deskew, dir_of_all=self.dir_of_all, f_name=self.f_name)
                slope_first = 0  # return_deskew_slop(cv2.erode(textline_mask_tot_ea, self.kernel, iterations=2),sigma, dir_of_all=self.dir_of_all, f_name=self.f_name)

                if self.dir_of_deskewed is not None:
                    self.save_deskewed_image(slope_deskew)
                # img_rotated=self.rotyate_image_different(self.image_org,slope_deskew)
                print(slope_deskew, "slope_deskew")

                ##plt.imshow(img_rotated)
                ##plt.show()
                ##sys.exit()
                print("deskewing: " + str(time.time() - t1))

                image_page_rotated, textline_mask_tot = image_page[:, :], textline_mask_tot_ea[:, :]  # rotation_not_90_func(image_page,textline_mask_tot_ea,slope_first)
                textline_mask_tot[mask_images[:, :] == 1] = 0

                pixel_img = 1
                min_area = 0.00001
                max_area = 0.0006
                textline_mask_tot_small_size = return_contours_of_interested_region_by_size(textline_mask_tot, pixel_img, min_area, max_area)

                # text_regions_p_1[(textline_mask_tot[:,:]==1) & (text_regions_p_1[:,:]==2)]=1

                text_regions_p_1[mask_lines[:, :] == 1] = 3

                ##text_regions_p_1[textline_mask_tot_small_size[:,:]==1]=1

                text_regions_p = text_regions_p_1[:, :]  # long_short_region[:,:]#self.get_regions_from_2_models(image_page)

                text_regions_p = np.array(text_regions_p)

                if num_col_classifier == 1 or num_col_classifier == 2:

                    try:
                        regions_without_seperators = (text_regions_p[:, :] == 1) * 1
                        regions_without_seperators = regions_without_seperators.astype(np.uint8)

                        text_regions_p = self.get_marginals(rotate_image(regions_without_seperators, slope_deskew), text_regions_p, num_col_classifier, slope_deskew)

                    except:
                        pass
                else:
                    pass

                # plt.imshow(text_regions_p)
                # plt.show()

                if self.dir_of_all is not None:
                    self.save_plot_of_layout_main_all(text_regions_p, image_page)
                if self.dir_of_layout is not None:
                    self.save_plot_of_layout_main(text_regions_p, image_page)

                print("marginals: " + str(time.time() - t1))

                if not self.full_layout:

                    if np.abs(slope_deskew) >= SLOPE_THRESHOLD:
                        image_page_rotated_n, textline_mask_tot_d, text_regions_p_1_n = rotation_not_90_func(image_page, textline_mask_tot, text_regions_p, slope_deskew)

                        text_regions_p_1_n = resize_image(text_regions_p_1_n, text_regions_p.shape[0], text_regions_p.shape[1])
                        textline_mask_tot_d = resize_image(textline_mask_tot_d, text_regions_p.shape[0], text_regions_p.shape[1])

                        regions_without_seperators_d = (text_regions_p_1_n[:, :] == 1) * 1

                    regions_without_seperators = (text_regions_p[:, :] == 1) * 1  # ( (text_regions_p[:,:]==1) | (text_regions_p[:,:]==2) )*1 #self.return_regions_without_seperators_new(text_regions_p[:,:,0],img_only_regions)

                    pixel_lines = 3
                    if np.abs(slope_deskew) < SLOPE_THRESHOLD:
                        num_col, peaks_neg_fin, matrix_of_lines_ch, spliter_y_new, seperators_closeup_n = find_number_of_columns_in_document(np.repeat(text_regions_p[:, :, np.newaxis], 3, axis=2), num_col_classifier, pixel_lines)

                    if np.abs(slope_deskew) >= SLOPE_THRESHOLD:
                        num_col_d, peaks_neg_fin_d, matrix_of_lines_ch_d, spliter_y_new_d, seperators_closeup_n_d = find_number_of_columns_in_document(np.repeat(text_regions_p_1_n[:, :, np.newaxis], 3, axis=2), num_col_classifier, pixel_lines)
                    K.clear_session()
                    gc.collect()

                    # print(peaks_neg_fin,num_col,'num_col2')

                    print(num_col_classifier, "num_col_classifier")

                    if num_col_classifier >= 3:
                        if np.abs(slope_deskew) < SLOPE_THRESHOLD:
                            regions_without_seperators = regions_without_seperators.astype(np.uint8)
                            regions_without_seperators = cv2.erode(regions_without_seperators[:, :], self.kernel, iterations=6)

                            random_pixels_for_image = np.random.randn(regions_without_seperators.shape[0], regions_without_seperators.shape[1])
                            random_pixels_for_image[random_pixels_for_image < -0.5] = 0
                            random_pixels_for_image[random_pixels_for_image != 0] = 1

                            regions_without_seperators[(random_pixels_for_image[:, :] == 1) & (text_regions_p[:, :] == 2)] = 1

                        if np.abs(slope_deskew) >= SLOPE_THRESHOLD:
                            regions_without_seperators_d = regions_without_seperators_d.astype(np.uint8)
                            regions_without_seperators_d = cv2.erode(regions_without_seperators_d[:, :], self.kernel, iterations=6)

                            random_pixels_for_image = np.random.randn(regions_without_seperators_d.shape[0], regions_without_seperators_d.shape[1])
                            random_pixels_for_image[random_pixels_for_image < -0.5] = 0
                            random_pixels_for_image[random_pixels_for_image != 0] = 1

                            regions_without_seperators_d[(random_pixels_for_image[:, :] == 1) & (text_regions_p_1_n[:, :] == 2)] = 1
                    else:
                        pass

                    if np.abs(slope_deskew) < SLOPE_THRESHOLD:
                        boxes = return_boxes_of_images_by_order_of_reading_new(spliter_y_new, regions_without_seperators, matrix_of_lines_ch)
                    else:
                        boxes_d = return_boxes_of_images_by_order_of_reading_new(spliter_y_new_d, regions_without_seperators_d, matrix_of_lines_ch_d)

                    # print(len(boxes),'boxes')

                    # sys.exit()

                    print("boxes in: " + str(time.time() - t1))
                    img_revised_tab = text_regions_p[:, :]

                    # plt.imshow(img_revised_tab)
                    # plt.show()
                    K.clear_session()

                pixel_img = 4
                min_area_mar = 0.00001
                polygons_of_marginals = return_contours_of_interested_region(text_regions_p, pixel_img, min_area_mar)

                if self.full_layout:
                    # set first model with second model
                    text_regions_p[:, :][text_regions_p[:, :] == 2] = 5
                    text_regions_p[:, :][text_regions_p[:, :] == 3] = 6
                    text_regions_p[:, :][text_regions_p[:, :] == 4] = 8

                    K.clear_session()
                    # gc.collect()

                    patches = True

                    image_page = image_page.astype(np.uint8)

                    # print(type(image_page))
                    regions_fully, regions_fully_only_drop = self.extract_text_regions(image_page, patches, cols=num_col_classifier)

                    regions_fully_only_drop = put_drop_out_from_only_drop_model(regions_fully_only_drop, text_regions_p)
                    regions_fully[:, :, 0][regions_fully_only_drop[:, :, 0] == 4] = 4
                    K.clear_session()
                    gc.collect()

                    # plt.imshow(regions_fully[:,:,0])
                    # plt.show()

                    regions_fully = putt_bb_of_drop_capitals_of_model_in_patches_in_layout(regions_fully)

                    # plt.imshow(regions_fully[:,:,0])
                    # plt.show()

                    K.clear_session()
                    gc.collect()
                    patches = False
                    regions_fully_np, _ = self.extract_text_regions(image_page, patches, cols=num_col_classifier)

                    # plt.imshow(regions_fully_np[:,:,0])
                    # plt.show()

                    if num_col_classifier > 2:
                        regions_fully_np[:, :, 0][regions_fully_np[:, :, 0] == 4] = 0
                    else:
                        regions_fully_np = filter_small_drop_capitals_from_no_patch_layout(regions_fully_np, text_regions_p)

                    # regions_fully_np=filter_small_drop_capitals_from_no_patch_layout(regions_fully_np,text_regions_p)
                    # plt.imshow(regions_fully_np[:,:,0])
                    # plt.show()

                    K.clear_session()
                    gc.collect()

                    # plt.imshow(regions_fully[:,:,0])
                    # plt.show()

                    regions_fully = boosting_headers_by_longshot_region_segmentation(regions_fully, regions_fully_np, img_only_regions)

                    # plt.imshow(regions_fully[:,:,0])
                    # plt.show()

                    text_regions_p[:, :][regions_fully[:, :, 0] == 4] = 4
                    ##text_regions_p[:,:][(regions_fully[:,:,0]==7) & (text_regions_p[:,:]!=0)]=7

                    text_regions_p[:, :][regions_fully_np[:, :, 0] == 4] = 4

                    # plt.imshow(text_regions_p)
                    # plt.show()

                    if np.abs(slope_deskew) >= SLOPE_THRESHOLD:
                        image_page_rotated_n, textline_mask_tot_d, text_regions_p_1_n, regions_fully_n = rotation_not_90_func_full_layout(image_page, textline_mask_tot, text_regions_p, regions_fully, slope_deskew)

                        text_regions_p_1_n = resize_image(text_regions_p_1_n, text_regions_p.shape[0], text_regions_p.shape[1])
                        textline_mask_tot_d = resize_image(textline_mask_tot_d, text_regions_p.shape[0], text_regions_p.shape[1])
                        regions_fully_n = resize_image(regions_fully_n, text_regions_p.shape[0], text_regions_p.shape[1])

                        regions_without_seperators_d = (text_regions_p_1_n[:, :] == 1) * 1

                    regions_without_seperators = (text_regions_p[:, :] == 1) * 1  # ( (text_regions_p[:,:]==1) | (text_regions_p[:,:]==2) )*1 #self.return_regions_without_seperators_new(text_regions_p[:,:,0],img_only_regions)

                    K.clear_session()
                    gc.collect()

                    img_revised_tab = np.copy(text_regions_p[:, :])

                    print("full layout in: " + str(time.time() - t1))

                # sys.exit()

                pixel_img = 5
                polygons_of_images = return_contours_of_interested_region(img_revised_tab, pixel_img)

                # plt.imshow(img_revised_tab)
                # plt.show()

                # print(img_revised_tab.shape,text_regions_p_1_n.shape)

                # text_regions_p_1_n=resize_image(text_regions_p_1_n,img_revised_tab.shape[0],img_revised_tab.shape[1])

                # print(np.unique(text_regions_p_1_n),'uni')
                text_only = ((img_revised_tab[:, :] == 1)) * 1
                if np.abs(slope_deskew) >= SLOPE_THRESHOLD:
                    text_only_d = ((text_regions_p_1_n[:, :] == 1)) * 1
                ##text_only_h=( (img_revised_tab[:,:,0]==2) )*1

                # print(text_only.shape,text_only_d.shape)
                # plt.imshow(text_only)
                # plt.show()

                # plt.imshow(text_only_d)
                # plt.show()

                min_con_area = 0.000005

                if np.abs(slope_deskew) >= SLOPE_THRESHOLD:

                    contours_only_text, hir_on_text = return_contours_of_image(text_only)
                    contours_only_text_parent = return_parent_contours(contours_only_text, hir_on_text)

                    areas_cnt_text = np.array([cv2.contourArea(contours_only_text_parent[j]) for j in range(len(contours_only_text_parent))])

                    areas_cnt_text = areas_cnt_text / float(text_only.shape[0] * text_only.shape[1])

                    contours_biggest = contours_only_text_parent[np.argmax(areas_cnt_text)]
                    contours_only_text_parent = [contours_only_text_parent[jz] for jz in range(len(contours_only_text_parent)) if areas_cnt_text[jz] > min_con_area]
                    areas_cnt_text_parent = [areas_cnt_text[jz] for jz in range(len(areas_cnt_text)) if areas_cnt_text[jz] > min_con_area]

                    index_con_parents = np.argsort(areas_cnt_text_parent)
                    contours_only_text_parent = list(np.array(contours_only_text_parent)[index_con_parents])
                    areas_cnt_text_parent = list(np.array(areas_cnt_text_parent)[index_con_parents])

                    cx_bigest_big, cy_biggest_big, _, _, _, _, _ = find_new_features_of_contoures([contours_biggest])
                    cx_bigest, cy_biggest, _, _, _, _, _ = find_new_features_of_contoures(contours_only_text_parent)

                    contours_only_text_d, hir_on_text_d = return_contours_of_image(text_only_d)
                    contours_only_text_parent_d = return_parent_contours(contours_only_text_d, hir_on_text_d)

                    areas_cnt_text_d = np.array([cv2.contourArea(contours_only_text_parent_d[j]) for j in range(len(contours_only_text_parent_d))])

                    areas_cnt_text_d = areas_cnt_text_d / float(text_only_d.shape[0] * text_only_d.shape[1])

                    contours_biggest_d = contours_only_text_parent_d[np.argmax(areas_cnt_text_d)]

                    cx_bigest_d_big, cy_biggest_d_big, _, _, _, _, _ = find_new_features_of_contoures([contours_biggest_d])
                    cx_bigest_d, cy_biggest_d, _, _, _, _, _ = find_new_features_of_contoures(contours_only_text_parent_d)

                    (h, w) = text_only.shape[:2]
                    center = (w // 2.0, h // 2.0)
                    M = cv2.getRotationMatrix2D(center, slope_deskew, 1.0)

                    M_22 = np.array(M)[:2, :2]

                    p_big = np.dot(M_22, [cx_bigest_big, cy_biggest_big])

                    x_diff = p_big[0] - cx_bigest_d_big
                    y_diff = p_big[1] - cy_biggest_d_big

                    # print(p_big)
                    # print(cx_bigest_d_big,cy_biggest_d_big)
                    # print(x_diff,y_diff)

                    contours_only_text_parent_d_ordered = []
                    for i in range(len(contours_only_text_parent)):
                        # img1=np.zeros((text_only.shape[0],text_only.shape[1],3))
                        # img1=cv2.fillPoly(img1,pts=[contours_only_text_parent[i]] ,color=(1,1,1))

                        # plt.imshow(img1[:,:,0])
                        # plt.show()

                        p = np.dot(M_22, [cx_bigest[i], cy_biggest[i]])
                        # print(p)
                        p[0] = p[0] - x_diff[0]
                        p[1] = p[1] - y_diff[0]
                        # print(p)
                        # print(cx_bigest_d)
                        # print(cy_biggest_d)
                        dists = [math.sqrt((p[0] - cx_bigest_d[j]) ** 2 + (p[1] - cy_biggest_d[j]) ** 2) for j in range(len(cx_bigest_d))]
                        # print(np.argmin(dists))
                        contours_only_text_parent_d_ordered.append(contours_only_text_parent_d[np.argmin(dists)])

                        # img2=np.zeros((text_only.shape[0],text_only.shape[1],3))
                        # img2=cv2.fillPoly(img2,pts=[contours_only_text_parent_d[np.argmin(dists)]] ,color=(1,1,1))

                        # plt.imshow(img2[:,:,0])
                        # plt.show()

                else:
                    contours_only_text, hir_on_text = return_contours_of_image(text_only)
                    contours_only_text_parent = return_parent_contours(contours_only_text, hir_on_text)

                    areas_cnt_text = np.array([cv2.contourArea(contours_only_text_parent[j]) for j in range(len(contours_only_text_parent))])

                    areas_cnt_text = areas_cnt_text / float(text_only.shape[0] * text_only.shape[1])

                    contours_biggest = contours_only_text_parent[np.argmax(areas_cnt_text)]
                    contours_only_text_parent = [contours_only_text_parent[jz] for jz in range(len(contours_only_text_parent)) if areas_cnt_text[jz] > min_con_area]
                    areas_cnt_text_parent = [areas_cnt_text[jz] for jz in range(len(areas_cnt_text)) if areas_cnt_text[jz] > min_con_area]

                    index_con_parents = np.argsort(areas_cnt_text_parent)
                    contours_only_text_parent = list(np.array(contours_only_text_parent)[index_con_parents])
                    areas_cnt_text_parent = list(np.array(areas_cnt_text_parent)[index_con_parents])

                    cx_bigest_big, cy_biggest_big, _, _, _, _, _ = find_new_features_of_contoures([contours_biggest])
                    cx_bigest, cy_biggest, _, _, _, _, _ = find_new_features_of_contoures(contours_only_text_parent)
                    # print(areas_cnt_text_parent,'areas_cnt_text_parent')

                    ###index_con_parents_d=np.argsort(areas_cnt_text_parent_d)
                    ##contours_only_text_parent_d=list(np.array(contours_only_text_parent_d)[index_con_parents_d])
                    ###areas_cnt_text_parent_d=list(np.array(areas_cnt_text_parent_d)[index_con_parents_d])

                    ##print(areas_cnt_text_parent_d,'areas_cnt_text_parent_d')

                    # print(len(contours_only_text_parent),len(contours_only_text_parent_d),'vizzz')

                txt_con_org = get_textregion_contours_in_org_image(contours_only_text_parent, self.image, slope_first)

                ###boxes_text,_= get_text_region_boxes_by_given_contours(contours_only_text_parent)
                boxes_text, _ = get_text_region_boxes_by_given_contours(contours_only_text_parent)
                boxes_marginals, _ = get_text_region_boxes_by_given_contours(polygons_of_marginals)
                ####boxes_text_h,_= get_text_region_boxes_by_given_contours(text_only_h,contours_only_text_parent_h,image_page)

                if not self.curved_line:
                    slopes, all_found_texline_polygons, boxes_text, txt_con_org, contours_only_text_parent, all_box_coord, index_by_text_par_con = self.get_slopes_and_deskew_new(txt_con_org, contours_only_text_parent, textline_mask_tot_ea, image_page_rotated, boxes_text, slope_deskew)

                    slopes_marginals, all_found_texline_polygons_marginals, boxes_marginals, _, polygons_of_marginals, all_box_coord_marginals, index_by_text_par_con_marginal = self.get_slopes_and_deskew_new(polygons_of_marginals, polygons_of_marginals, textline_mask_tot_ea, image_page_rotated, boxes_marginals, slope_deskew)

                if self.curved_line:
                    scale_param = 1
                    all_found_texline_polygons, boxes_text, txt_con_org, contours_only_text_parent, all_box_coord, index_by_text_par_con, slopes = self.get_slopes_and_deskew_new_curved(txt_con_org, contours_only_text_parent, cv2.erode(textline_mask_tot_ea, kernel=self.kernel, iterations=1), image_page_rotated, boxes_text, text_only, num_col_classifier, scale_param, slope_deskew)

                    # all_found_texline_polygons,boxes_text,txt_con_org,contours_only_text_parent,all_box_coord=self.get_slopes_and_deskew_new_curved(txt_con_org,contours_only_text_parent,textline_mask_tot_ea,image_page_rotated,boxes_text,text_only,num_col,scale_param)
                    all_found_texline_polygons = small_textlines_to_parent_adherence2(all_found_texline_polygons, textline_mask_tot_ea, num_col_classifier)

                    # slopes=list(np.zeros(len(contours_only_text_parent)))

                    all_found_texline_polygons_marginals, boxes_marginals, _, polygons_of_marginals, all_box_coord_marginals, index_by_text_par_con_marginal, slopes_marginals = self.get_slopes_and_deskew_new_curved(polygons_of_marginals, polygons_of_marginals, cv2.erode(textline_mask_tot_ea, kernel=self.kernel, iterations=1), image_page_rotated, boxes_marginals, text_only, num_col_classifier, scale_param, slope_deskew)

                    # all_found_texline_polygons,boxes_text,txt_con_org,contours_only_text_parent,all_box_coord=self.get_slopes_and_deskew_new_curved(txt_con_org,contours_only_text_parent,textline_mask_tot_ea,image_page_rotated,boxes_text,text_only,num_col,scale_param)
                    all_found_texline_polygons_marginals = small_textlines_to_parent_adherence2(all_found_texline_polygons_marginals, textline_mask_tot_ea, num_col_classifier)

                index_of_vertical_text_contours = np.array(range(len(slopes)))[(abs(np.array(slopes)) > 60)]

                contours_text_vertical = [contours_only_text_parent[i] for i in index_of_vertical_text_contours]

                K.clear_session()
                gc.collect()

                # contours_only_text_parent_d_ordered=list(np.array(contours_only_text_parent_d_ordered)[index_by_text_par_con])
                ###print(index_by_text_par_con,'index_by_text_par_con')

                if self.full_layout:
                    ##for iii in range(len(contours_only_text_parent)):
                    ##img1=np.zeros((text_only.shape[0],text_only.shape[1],3))
                    ##img1=cv2.fillPoly(img1,pts=[contours_only_text_parent[iii]] ,color=(1,1,1))

                    ##plt.imshow(img1[:,:,0])
                    ##plt.show()

                    ##img2=np.zeros((text_only.shape[0],text_only.shape[1],3))
                    ##img2=cv2.fillPoly(img2,pts=[contours_only_text_parent_d_ordered[iii]] ,color=(1,1,1))

                    ##plt.imshow(img2[:,:,0])
                    ##plt.show()

                    if np.abs(slope_deskew) >= SLOPE_THRESHOLD:
                        contours_only_text_parent_d_ordered = list(np.array(contours_only_text_parent_d_ordered)[index_by_text_par_con])

                        text_regions_p, contours_only_text_parent, contours_only_text_parent_h, all_box_coord, all_box_coord_h, all_found_texline_polygons, all_found_texline_polygons_h, slopes, slopes_h, contours_only_text_parent_d_ordered, contours_only_text_parent_h_d_ordered = check_any_text_region_in_model_one_is_main_or_header(text_regions_p, regions_fully, contours_only_text_parent, all_box_coord, all_found_texline_polygons, slopes, contours_only_text_parent_d_ordered)
                    else:
                        contours_only_text_parent_d_ordered = None

                        text_regions_p, contours_only_text_parent, contours_only_text_parent_h, all_box_coord, all_box_coord_h, all_found_texline_polygons, all_found_texline_polygons_h, slopes, slopes_h, contours_only_text_parent_d_ordered, contours_only_text_parent_h_d_ordered = check_any_text_region_in_model_one_is_main_or_header(text_regions_p, regions_fully, contours_only_text_parent, all_box_coord, all_found_texline_polygons, slopes, contours_only_text_parent_d_ordered)

                    ###text_regions_p,contours_only_text_parent,contours_only_text_parent_h,all_box_coord,all_box_coord_h,all_found_texline_polygons,all_found_texline_polygons_h=check_any_text_region_in_model_one_is_main_or_header(text_regions_p,regions_fully,contours_only_text_parent,all_box_coord,all_found_texline_polygons)
                    # text_regions_p=self.return_region_segmentation_after_implementing_not_head_maintext_parallel(text_regions_p,boxes)

                    # if you want to save the layout result just uncommet following plot

                    if self.dir_of_layout is not None:
                        self.save_plot_of_layout(text_regions_p, image_page)
                    if self.dir_of_all is not None:
                        self.save_plot_of_layout_all(text_regions_p, image_page)

                    K.clear_session()
                    gc.collect()

                    ##print('Job done in: '+str(time.time()-t1))

                    polygons_of_tabels = []

                    pixel_img = 4
                    polygons_of_drop_capitals = return_contours_of_interested_region_by_min_size(text_regions_p, pixel_img)
                    # polygons_of_drop_capitals=[]

                    all_found_texline_polygons = self.adhere_drop_capital_region_into_cprresponding_textline(text_regions_p, polygons_of_drop_capitals, contours_only_text_parent, contours_only_text_parent_h, all_box_coord, all_box_coord_h, all_found_texline_polygons, all_found_texline_polygons_h)

                    # print(len(contours_only_text_parent_h),len(contours_only_text_parent_h_d_ordered),'contours_only_text_parent_h')
                    pixel_lines = 6

                    if not self.headers_off:
                        if np.abs(slope_deskew) < SLOPE_THRESHOLD:
                            num_col, peaks_neg_fin, matrix_of_lines_ch, spliter_y_new, seperators_closeup_n = find_number_of_columns_in_document(np.repeat(text_regions_p[:, :, np.newaxis], 3, axis=2), num_col_classifier, pixel_lines, contours_only_text_parent_h)
                        else:
                            num_col_d, peaks_neg_fin_d, matrix_of_lines_ch_d, spliter_y_new_d, seperators_closeup_n_d = find_number_of_columns_in_document(np.repeat(text_regions_p_1_n[:, :, np.newaxis], 3, axis=2), num_col_classifier, pixel_lines, contours_only_text_parent_h_d_ordered)
                    elif self.headers_off:
                        if np.abs(slope_deskew) < SLOPE_THRESHOLD:
                            num_col, peaks_neg_fin, matrix_of_lines_ch, spliter_y_new, seperators_closeup_n = find_number_of_columns_in_document(np.repeat(text_regions_p[:, :, np.newaxis], 3, axis=2), num_col_classifier, pixel_lines)
                        else:
                            num_col_d, peaks_neg_fin_d, matrix_of_lines_ch_d, spliter_y_new_d, seperators_closeup_n_d = find_number_of_columns_in_document(np.repeat(text_regions_p_1_n[:, :, np.newaxis], 3, axis=2), num_col_classifier, pixel_lines)

                    # print(peaks_neg_fin,peaks_neg_fin_d,'num_col2')

                    # print(spliter_y_new,spliter_y_new_d,'num_col_classifier')

                    # print(matrix_of_lines_ch.shape,matrix_of_lines_ch_d.shape,'matrix_of_lines_ch')

                    if num_col_classifier >= 3:

                        if np.abs(slope_deskew) < SLOPE_THRESHOLD:
                            regions_without_seperators = regions_without_seperators.astype(np.uint8)
                            regions_without_seperators = cv2.erode(regions_without_seperators[:, :], self.kernel, iterations=6)

                            random_pixels_for_image = np.random.randn(regions_without_seperators.shape[0], regions_without_seperators.shape[1])
                            random_pixels_for_image[random_pixels_for_image < -0.5] = 0
                            random_pixels_for_image[random_pixels_for_image != 0] = 1

                            regions_without_seperators[(random_pixels_for_image[:, :] == 1) & (text_regions_p[:, :] == 5)] = 1

                        else:

                            regions_without_seperators_d = regions_without_seperators_d.astype(np.uint8)
                            regions_without_seperators_d = cv2.erode(regions_without_seperators_d[:, :], self.kernel, iterations=6)

                            random_pixels_for_image = np.random.randn(regions_without_seperators_d.shape[0], regions_without_seperators_d.shape[1])
                            random_pixels_for_image[random_pixels_for_image < -0.5] = 0
                            random_pixels_for_image[random_pixels_for_image != 0] = 1

                            regions_without_seperators_d[(random_pixels_for_image[:, :] == 1) & (text_regions_p_1_n[:, :] == 5)] = 1
                    else:
                        pass

                    if np.abs(slope_deskew) < SLOPE_THRESHOLD:
                        boxes = return_boxes_of_images_by_order_of_reading_new(spliter_y_new, regions_without_seperators, matrix_of_lines_ch)
                    else:
                        boxes_d = return_boxes_of_images_by_order_of_reading_new(spliter_y_new_d, regions_without_seperators_d, matrix_of_lines_ch_d)

                # print(slopes)
                if self.dir_of_cropped_images is not None:
                    self.write_images_into_directory(polygons_of_images, self.dir_of_cropped_images, image_page)

                if self.full_layout:
                    if np.abs(slope_deskew) < SLOPE_THRESHOLD:
                        order_text_new, id_of_texts_tot = self.do_order_of_regions(contours_only_text_parent, contours_only_text_parent_h, boxes, textline_mask_tot)
                    else:
                        order_text_new, id_of_texts_tot = self.do_order_of_regions(contours_only_text_parent_d_ordered, contours_only_text_parent_h_d_ordered, boxes_d, textline_mask_tot_d)

                    self.write_into_page_xml_full(contours_only_text_parent, contours_only_text_parent_h, page_coord, self.dir_out, order_text_new, id_of_texts_tot, all_found_texline_polygons, all_found_texline_polygons_h, all_box_coord, all_box_coord_h, polygons_of_images, polygons_of_tabels, polygons_of_drop_capitals, polygons_of_marginals, all_found_texline_polygons_marginals, all_box_coord_marginals, slopes, slopes_marginals)
                else:
                    contours_only_text_parent_h = None
                    # print('bura galmir?')
                    if np.abs(slope_deskew) < SLOPE_THRESHOLD:
                        contours_only_text_parent = list(np.array(contours_only_text_parent)[index_by_text_par_con])
                        order_text_new, id_of_texts_tot = self.do_order_of_regions(contours_only_text_parent, contours_only_text_parent_h, boxes, textline_mask_tot)
                    else:
                        contours_only_text_parent_d_ordered = list(np.array(contours_only_text_parent_d_ordered)[index_by_text_par_con])
                        order_text_new, id_of_texts_tot = self.do_order_of_regions(contours_only_text_parent_d_ordered, contours_only_text_parent_h, boxes_d, textline_mask_tot_d)
                    # order_text_new , id_of_texts_tot=self.do_order_of_regions(contours_only_text_parent,contours_only_text_parent_h,boxes,textline_mask_tot)
                    self.write_into_page_xml(txt_con_org, page_coord, self.dir_out, order_text_new, id_of_texts_tot, all_found_texline_polygons, all_box_coord, polygons_of_images, polygons_of_marginals, all_found_texline_polygons_marginals, all_box_coord_marginals, self.curved_line, slopes, slopes_marginals)

            except:
                txt_con_org = []
                order_text_new = []
                id_of_texts_tot = []
                all_found_texline_polygons = []
                all_box_coord = []
                polygons_of_images = []
                polygons_of_marginals = []
                all_found_texline_polygons_marginals = []
                all_box_coord_marginals = []
                slopes = []
                slopes_marginals = []
                self.write_into_page_xml(txt_con_org, page_coord, self.dir_out, order_text_new, id_of_texts_tot, all_found_texline_polygons, all_box_coord, polygons_of_images, polygons_of_marginals, all_found_texline_polygons_marginals, all_box_coord_marginals, self.curved_line, slopes, slopes_marginals)

        print("Job done in: " + str(time.time() - t1))

