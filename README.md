NOTE: The $ symbol means that the text that follows must be executed in terminal. All other instructions without a $ you need to do manually (e.g. downloading some stuff and putting it into some folder).

01. $ conda create -n MCGaze python=3.9
02. $ conda activate MCGaze
03. $ pip install torch==1.10.0+cu113 torchvision==0.11.1+cu113 torchaudio==0.10.0 -f https://download.pytorch.org/whl/torch_stable.html<br>
Note that the official MCGaze github page recommends to:<br>
$ pip install torch==1.7.1+cu110 torchvision==0.8.2+cu110 torchaudio==0.7.2 -f https://download.pytorch.org/whl/torch_stable.html<br>
But **don't do this**! You will probably not be able to run the MCGaze demo for the reason outlined under step 4 (see below).
04. $ MMCV_WITH_OPS=1 FORCE_CUDA=1 pip install mmcv-full==1.4.0 -f https://download.openmmlab.com/mmcv/dist/cu113/torch1.10.0/index.html<br>
The official MCGaze github page tells you to install the following:<br>
$ pip install mmcv-full==1.4.8 -f https://download.openmmlab.com/mmcv/dist/cu110/torch1.7.1/index.html<br>
But **don't do this**! With torch 1.7.1 and mmcv-full 1.4.8 the MMCV CUDA Compiler ($ python MCGaze/mmdet/utils/collect_env.py) doesn't get installed! Adding MMCV_WITH_OPS=1 FORCE_CUDA=1 in this case is not helping either.
05. $ git clone https://github.com/Frankninetytwo/MCGaze.git
06. $ cd MCGaze
07. $ pip install -v -e .
08. $ pip install requests
09. $ pip install facenet_pytorch
10. $ pip install seaborn
11. download https://drive.google.com/file/d/1ru0xhuB5N9kwvN9XLvZMQvVSfOgtbxmq/view?usp=drive_link
12. put downloaded multiclue_gaze_r50_gaze360.pth into MCGaze/ckpts folder
13. download https://drive.google.com/file/d/1gglIwqxaH2iTvy6lZlXuAcMpd_U0GCUb/view?usp=sharing
14. put downloaded crowdhuman_yolov5m.pt into MCGaze/MCGaze_demo folder
15. $ cd MCGaze_demo
16. $ mkdir frames
17. $ mkdir new_frames
18. $ mkdir result
19. $ mkdir result/labels<br>
**NOTE**: do not put anything inside the above created folders, not even .gitkeep (hence need to create folders manually)! Their demo code determines frame count n of a video by the amount of images inside these folders. If there is another file inside such folder then the program will try to analyze a file with name "n+1.jpg", which obviously doesn't exist, because the video has only n frames!

Feature extraction works exactly the same way as in my L2CS-Net repo. It's explained at the end of that repo's README.md. The only difference is that the MCGaze feature extraction scripts are not located in the main folder, but in MCGaze/MCGaze_demo.
