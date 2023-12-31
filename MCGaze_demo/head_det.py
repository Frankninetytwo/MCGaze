# This script is based on MCGaze/MCGaze_demo/head_det.py of https://github.com/zgchen33/mcgaze.

import sys
from pathlib import Path
sys.path.append(str(Path.cwd()) + '/yolo_head')
from yolo_head.detect import det_head
## 构建字典，遍历每张图片
import cv2
import os
import argparse


def parse_args():

    parser = argparse.ArgumentParser(description='Determining positions of human heads in a video for each frame')
    parser.add_argument('--weights', nargs='+', type=str, default=str(Path.cwd()) + '/crowdhuman_yolov5m.pt', help='model.pt path(s)')
    parser.add_argument('--source', type=str, default=str(Path.cwd()) + '/frames/*.jpg', help='source')  # file/folder, 0 for webcam
    parser.add_argument('--img-size', type=int, default=640, help='inference size (pixels)')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='object confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='IOU threshold for NMS')
    parser.add_argument('--device', default='', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument('--view-img', action='store_true', help='display results')
    parser.add_argument('--save-txt', action='store_true', help='save results to *.txt')
    parser.add_argument('--save-conf', action='store_true', help='save confidences in --save-txt labels')
    parser.add_argument('--classes', nargs='+', type=int, help='filter by class: --class 0, or --class 0 2 3')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--augment', action='store_true', help='augmented inference')
    parser.add_argument('--update', action='store_true', help='update all models')
    parser.add_argument('--project', default='runs/detect', help='save results to project/name')
    parser.add_argument('--name', default='exp', help='save results to project/name')
    parser.add_argument('--exist-ok', action='store_true', help='existing project/name ok, do not increment')
    parser.add_argument('--person', action='store_true', help='displays only person')
    parser.add_argument('--heads', action='store_true', help='displays only person')
    # This argument did't exist before, had to add it myself. Also had to move the argument parsing from yolo_head/detect.py to this file.
    parser.add_argument('--video', dest='video_path', help='path of the video to proccess', type=str)
    
    return parser.parse_args()


def delete_files_in_folder(folder_path):
    # 检查文件夹是否存在
    if not os.path.exists(folder_path):
        print(f"Can't delete the files in '{folder_path}', because this path doesn't exist.")
        return

    # 获取文件夹中的所有文件和子文件夹
    files = os.listdir(folder_path)

    for file in files:
        file_path = os.path.join(folder_path, file)

        if os.path.isfile(file_path):
            # 如果是文件，删除它
            os.remove(file_path)
        elif os.path.isdir(file_path):
            # 如果是文件夹，递归删除它
            delete_files_in_folder(file_path)
    
    # 删除空文件夹


if __name__ == '__main__':

    args = parse_args()

    if (not args.video_path):
        print('argument --video required')
        exit()

    video_capture = cv2.VideoCapture(args.video_path)

    # Check if the file opened correctly
    if not video_capture.isOpened():
        raise IOError('Failed to open video file \"' + args.video_path + '\"')
    

    # Delete the files that were generated by head_det.py and demo.py during processing
    # of a prior video.
    delete_files_in_folder(str(Path.cwd()) + '/result/labels/')
    delete_files_in_folder(str(Path.cwd()) + '/frames/')
    delete_files_in_folder(str(Path.cwd()) + '/new_frames/')
    # Also delete the file that stored the name of last processed video.
    if(os.path.exists('result/processed_video.txt')):
        os.remove('result/processed_video.txt')


    frame_id = 0

    while   True:
        ret, frame = video_capture.read()
        if ret:
            cv2.imwrite(str(Path.cwd()) + '/frames/%d.jpg' % frame_id, frame)
            frame_id += 1
        else:
            break
        

    det_head(args)

    # Each video is analyzed by calling two different scripts:
    # 1. head_det.py
    # It splits up the video into frames, saving them as 0.jpg, 1.jpg, ...
    # In the next step it detects human heads in each of the images and creates for each image/frame
    # a file that contains the head positions (0.txt, 1.txt, ...).
    # 2. demo.py
    # This script estimates gaze using the files created by head_det.py; it doesn't know the video
    # where the images/frames were extracted from. Hence, if we want to analyze multiple videos and
    # write the estimated gaze to .csv files with the same name as the videos we need to store the
    # path of the currently processed video somewhere so that demo.py can read it.
    with open(str(Path.cwd()) + '/result/processed_video.txt', 'w') as f:
        f.write('second line: path of processed video, third line: fps of processed video\n')
        f.write(args.video_path + '\n' + str(video_capture.get(cv2.CAP_PROP_FPS)))

    video_capture.release()