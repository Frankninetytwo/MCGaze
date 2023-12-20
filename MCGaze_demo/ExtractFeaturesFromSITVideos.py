import os

if __name__ == '__main__':


    # This list needs to be fill with paths to each SIT video file, e.g.
    # paths_of_SIT_videos = [ 'Path_to_SIT_Videos/Participant_1/videoname.mp4', 'Path_to_SIT_Videos/Participant_2/videoname.avi', ... ]
    paths_of_SIT_videos = []

    

    # verify that the list contents are indeed valid files
    for video_path in paths_of_SIT_videos:
        if not os.path.isfile(video_path):
            print('The path \"' + video_path + '\" from the list named \"paths_of_SIT_videos\" is not a file!\n')
            exit()

    for video_path in paths_of_SIT_videos:
        print("\nanalyzing video \"{}\"".format(video_path))
        os.system("python3 ExtractFeatures.py --video {}".format(video_path))