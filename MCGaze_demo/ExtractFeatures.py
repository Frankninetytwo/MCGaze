import os
import argparse

def parse_args():

    parser = argparse.ArgumentParser(description='Estimate gazes in a video using pretrained model')
    
    parser.add_argument(
        '--video',
        dest='video_path',
        help='path of the video to proccess',  
        type=str
        )
    
    parser.add_argument(
        '--timestamp-to-start-at',
        dest='timestamp_to_start_at',
        help='point in time of the video from which on gaze shall be estimated (in seconds)',  
        type=float,
        default=0.0
    )
    
    parser.add_argument(
        '-v',
        help='visualize output (creates a new video with estimated gaze)',
        action='store_true'
        )
    
    return parser.parse_args()


if __name__ == '__main__':
    
    args = parse_args()

    if (not args.video_path):
        print('argument --video required')
        exit()

    os.system('python3 head_det.py --video {}'.format(args.video_path))
    os.system('python3 demo.py {}{}'.format(args.timestamp_to_start_at, ' -v' if args.v else ''))