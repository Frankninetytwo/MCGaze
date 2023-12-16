# This script is based on MCGaze/MCGaze_demo/demo.ipynb of https://github.com/zgchen33/mcgaze.
# All English comments were added by me (Frank Schilling) to understand the code better.
# Note: If there is more than one human head detected in a video frame then the estimated gaze
# for that frame in Output/processed_video.csv will be nan!

import cv2
from facenet_pytorch import MTCNN
import os

from pathlib import Path

from mmdet.apis import init_detector
from mmdet.datasets.pipelines import Compose
import torch
from mmcv.parallel import collate, scatter
import numpy as np

import math
import argparse



def parse_args():

    parser = argparse.ArgumentParser(description='Estimate gaze of images generated by head_det.py')
    
    parser.add_argument(
        '-v',
        help='visualize output (creates a new video with estimated gaze)',
        action='store_true'
        )
    
    return parser.parse_args()


# Returns information about the video that was preprocessed by head_det.py:
# 1. the path of the video (otherwise this script wouldn't know which video it analyzes,
#    because it just works with the images of each video frame that were generated by head_det.py)
# 2. the FPS of the video
def get_source_video_info():
    with open('result/processed_video.txt', 'r') as f:
        # Discard first line as it is just a description of the contents.
        f.readline()
        source_video_path = f.readline()
        fps = float(f.readline())
        
        return source_video_path, fps


# File will be written to
# CWD/Output/filename_of_video_without_file_extension.csv
# where filename_of_video_without_file_extension is a parameter of this function.
def write_estimated_gaze_to_file(filename_of_video_without_file_extension, video_clip_list, video_fps):

    output_path = str(Path.cwd()) + '/Output/' + filename_of_video_without_file_extension + '.csv'
    
    with open(output_path, 'w') as f:
        
        #f.write('frame,timestamp in s,yaw in radians,pitch in radians\n')
        f.write('frame,timestamp in s,unknown 1,unknown 2\n')

        for current_frame in range(0, len(video_clip_list)):
            print('{},{},{},{}\n'.format(
                current_frame+1,
                round((current_frame) * (1.0 / video_fps), 3), # +/- 0.001 radians (less 0.1 degrees) can be rounded off (easier to compare output file to output from OpenFace)
                # Write nan to file if there is more than one human head found in the current frame. In this case I don't know whose gaze to estimate.
                math.nan if ('gaze_p1' in video_clip_list[current_frame]) else video_clip_list[current_frame]['gaze_p0']
                ))
            """
            f.write('{},{},{},{}\n'.format(
                current_frame+1,
                round((current_frame) * (1.0 / video_fps), 3), # +/- 0.001 radians (less 0.1 degrees) can be rounded off (easier to compare output file to output from OpenFace)
                # Write nan to file if there is more than one human head found in the current frame. In this case I don't know whose gaze to estimate.
                math.nan if ('gaze_p1' in video_clip_list[current_frame]) else video_clip_list[current_frame]['gaze_p0'][0][0],
                math.nan if ('gaze_p1' in video_clip_list[current_frame]) else video_clip_list[current_frame]['gaze_p0'][0][1]
                ))
            """


def load_datas(data, test_pipeline, datas):
    datas.append(test_pipeline(data))


def infer(datas,model,clip,i):
    datas = sorted(datas, key=lambda x:x['img_metas'].data['filename']) # 按帧顺序 img名称从小到大
    datas = collate(datas, samples_per_gpu=len(frame_id)) # 用来形成batch用的
    datas['img_metas'] = datas['img_metas'].data
    datas['img'] = datas['img'].data
    datas = scatter(datas, ["cuda:0"])[0]
    with torch.no_grad():
        (det_bboxes, det_labels), det_gazes = model(
                return_loss=False,
                rescale=True,
                format=False,# 返回的bbox既包含face_bboxes也包含head_bboxes
                **datas)    # 返回的bbox格式是[x1,y1,x2,y2],根据return_loss函数来判断是forward_train还是forward_test.
    gaze_dim = det_gazes['gaze_score'].size(1)
    det_fusion_gaze = det_gazes['gaze_score'].view((det_gazes['gaze_score'].shape[0], 1, gaze_dim))
    clip['gaze_p'+str(i)].append(det_fusion_gaze.cpu().numpy())
    print("det_fusion_gaze =", det_fusion_gaze, "\ngaze_dim =", gaze_dim)



if __name__ == '__main__':

    args = parse_args()

    frame_id = 0
    person_num = 0
    video_clip=None
    # List of dictionaries where each dictionary represents one frame of the video.
    # I have commented the loops below, explaining exactly what data each loop writes into this list.
    video_clip_set = []
    vid_len = len(os.listdir(str(Path.cwd()) + '/frames'))
    # This loop fills the list video_clip_set with dictionaries of following structure:
    # dictionary['frame_id'][0] holds the index of the frame (as you can see by the [0] indexing
    # dictionary['frame_id'] seems to be a list for some reason, but it holds only 1 element). 
    # dictionary['person_num'] stores the amount of human heads that could be found in that frame.
    # If the amount of human heads in the next frame hasn't changed, then the dictionary doesn't contain
    # the key 'person_num'.
    # dictionary['p0'], dictionary['p1'], ... hold the position (min and max of x and y coordinates)
    # of the corresponding human head p0, p1, ... in the current video frame.
    while frame_id < vid_len:
        frame = cv2.imread(str(Path.cwd()) + ('/frames/%d.jpg' % frame_id))
        w,h,c = frame.shape
        txt_path = str(Path.cwd()) + ('/result/labels/%d.txt' % frame_id)
        f = open(txt_path, 'r')
        # Contains the positions (min and max of x and y coordinates) of every human head that could be detected in
        # the current frame. This data is aquired from the result/labels folder that is produced by head_det.py.
        face_bbox = []
        for line in f.readlines():
            line = line.strip()
            line = line.split(' ')
            for i in range(len(line)):
                line[i] = eval(line[i])
                #将每一行的数据存入字典
            if line[0]==1:
                face_bbox.append([(line[1]),(line[2]),(line[3]),(line[4])])
        f.close()
        #按第一维排序
        if face_bbox is not None:
            face_bbox = sorted(face_bbox, key= lambda x :x[0])
            cur_person_num = len(face_bbox)
        else:
            cur_person_num = 0
        if cur_person_num != person_num :
            if video_clip==None:
                video_clip={'frame_id': [], 'person_num': cur_person_num}
                video_clip['frame_id'].append(frame_id)
                for i in range(cur_person_num):
                    video_clip['p'+str(i)]=[face_bbox[i]]
            else:
                video_clip_set.append(video_clip)
                video_clip={'frame_id': [], 'person_num': cur_person_num}
                video_clip['frame_id'].append(frame_id)
                for i in range(cur_person_num):
                    video_clip['p'+str(i)]=[face_bbox[i]]
        else:
            video_clip['frame_id'].append(frame_id)
            for i in range(cur_person_num):
                    video_clip['p'+str(i)].append(face_bbox[i])
        person_num = cur_person_num
        frame_id += 1

    video_clip_set.append(video_clip)




    model = init_detector(
            os.path.dirname(str(Path.cwd())) + '/configs/multiclue_gaze/multiclue_gaze_r50_gaze360.py',
            os.path.dirname(str(Path.cwd())) + '/ckpts/multiclue_gaze_r50_gaze360.pth',
            device="cuda:0",
            cfg_options=None,)
    cfg = model.cfg




    print(cfg.data.test.pipeline[1:])
    test_pipeline = Compose(cfg.data.test.pipeline[1:])




    max_len = 100

    # This loop adds to each dictionary of the list video_clip_set the keys
    # 'gaze_p0', 'gaze_p1', ... where the corresponding value is the estimated
    # gaze of the corresponding human head p0, p1, ... in the current video frame.
    for clip in video_clip_set:
        frame_id = clip['frame_id']
        person_num = clip['person_num']
        for i in range(person_num):
            head_bboxes = clip['p'+str(i)]
            clip['gaze_p'+str(i)] = []
            datas = []
            for j,frame in enumerate(frame_id):
                cur_img = cv2.imread(str(Path.cwd()) + "/frames/"+str(frame)+".jpg")
                w,h,_ = cur_img.shape
                for xy in head_bboxes[j]:
                    xy = int(xy)
                head_center = [int(head_bboxes[j][1]+head_bboxes[j][3])//2,int(head_bboxes[j][0]+head_bboxes[j][2])//2]
                l = int(max(head_bboxes[j][3]-head_bboxes[j][1],head_bboxes[j][2]-head_bboxes[j][0])*0.8)
                head_crop = cur_img[max(0,head_center[0]-l):min(head_center[0]+l,w),max(0,head_center[1]-l):min(head_center[1]+l,h),:]
                w_n,h_n,_ = head_crop.shape
                # if frame==0:
                #     plt.imshow(head_crop)
                # print(head_crop.shape)
                cur_data = dict(filename=j,ori_filename=111,img=head_crop,img_shape=(w_n,h_n,3),ori_shape=(2*l,2*l,3),img_fields=['img'])
                load_datas(cur_data,test_pipeline,datas)
                # Not sure what the purpose of max_len or the loops index j is, because
                # clip['frame_id'] should always be of length 1 as it represents one frame,
                # hence j should always be 0 and the below if statement becomes always true. 
                if len(datas)>max_len or j==(len(frame_id)-1):
                    infer(datas,model,clip,i)
                    datas = []
                    if j==(len(frame_id)-1):
                        clip['gaze_p'+str(i)] = np.concatenate(clip['gaze_p'+str(i)],axis=0)




    for vid_clip in video_clip_set:
        for i,frame_id in enumerate(vid_clip['frame_id']):  # 遍历每一帧
            cur_img = cv2.imread(str(Path.cwd()) + "/frames/"+str(vid_clip['frame_id'][i])+".jpg")
            for j in range(vid_clip['person_num']):  # 遍历每一个人
                gaze = vid_clip['gaze_p'+str(j)][i][0]
                head_bboxes = vid_clip['p'+str(j)][i]
                for xy in head_bboxes:
                    xy = int(xy)
                head_center = [int(head_bboxes[1]+head_bboxes[3])//2,int(head_bboxes[0]+head_bboxes[2])//2]
                l = int(max(head_bboxes[3]-head_bboxes[1],head_bboxes[2]-head_bboxes[0])*1)
                gaze_len = l*1.0
                thick = max(5,int(l*0.01))
                cv2.arrowedLine(cur_img,(head_center[1],head_center[0]),
                            (int(head_center[1]-gaze_len*gaze[0]),int(head_center[0]-gaze_len*gaze[1])),
                            (230,253,11),thickness=thick)
            cv2.imwrite(str(Path.cwd()) + '/new_frames/%d.jpg' % frame_id, cur_img)




    img = cv2.imread(str(Path.cwd()) + '/new_frames/0.jpg')  #读取第一张图片
    source_video_path, video_fps = get_source_video_info()
    imgInfo = img.shape
    size = (imgInfo[1],imgInfo[0])  #获取图片宽高度信息
    print(size)


    write_estimated_gaze_to_file(Path(source_video_path).stem, video_clip_set, video_fps)


    if args.v:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        videoWrite = cv2.VideoWriter(str(Path.cwd()) + '/Output/' + Path(source_video_path).stem + '.mp4',fourcc,video_fps,size)
        files = os.listdir(str(Path.cwd()) + '/new_frames/')
        out_num = len(files)
        for i in range(0,out_num):
            fileName = str(Path.cwd()) + '/new_frames/'+str(i)+'.jpg'    #循环读取所有的图片,假设以数字顺序命名
            img = cv2.imread(fileName)
        
            videoWrite.write(img)# 将图片写入所创建的视频对象

        videoWrite.release()