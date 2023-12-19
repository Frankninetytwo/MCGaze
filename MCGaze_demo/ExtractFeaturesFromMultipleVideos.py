import argparse
import os
from os.path import isfile

def parse_args():

    parser = argparse.ArgumentParser(description='Estimate gazes in videos using pretrained model')
    
    parser.add_argument(
        '--videos',
        dest='videos_path',
        help='path of folder containing all the videos to proccess',  
        type=str
        )
    
    parser.add_argument(
        '-v',
        help='visualize output (creates a new video with estimated gaze for each input video)',
        action='store_true'
        )
    
    return parser.parse_args()

if __name__ == '__main__':

    args = parse_args()

    if not args.videos_path:
        print('argument --videos required')
        exit()

    if not os.path.isdir(args.videos_path):
        print('argument --videos invalid: \"' + args.videos_path + '\" is not a directory!')
        exit()


    filenames = []
    
    for file_or_folder in os.listdir(args.videos_path):
        if isfile(args.videos_path + '/' + file_or_folder):
            filenames.append(file_or_folder)

    for filename in filenames:
        print("analyzing file \"{}\"".format(filename))
        os.system("python3 ExtractFeatures.py --video {}{}".format(args.videos_path + '/' + filename, " -v" if args.v else ""))