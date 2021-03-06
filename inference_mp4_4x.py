import os
import cv2
import torch
import argparse
import numpy as np
from tqdm import tqdm
from torch.nn import functional as F

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
if torch.cuda.is_available():
    torch.set_grad_enabled(False)
    torch.backends.cudnn.enabled = True
    torch.backends.cudnn.benchmark = True

parser = argparse.ArgumentParser(description='Interpolation for a pair of images')
parser.add_argument('--video', dest='video', required=True)
parser.add_argument('--montage', dest='montage', action='store_true', help='montage origin video')
parser.add_argument('--model', dest='model', type=str, default='RIFE')
args = parser.parse_args()

if args.model == '2F':
    from model.RIFE2F import Model
else:
    from model.RIFE import Model
model = Model()
model.load_model('./train_log')
model.eval()
model.device()

videoCapture = cv2.VideoCapture(args.video)
fps = np.round(videoCapture.get(cv2.CAP_PROP_FPS))
success, frame = videoCapture.read()
h, w, _ = frame.shape
ph = ((h - 1) // 32 + 1) * 32
pw = ((w - 1) // 32 + 1) * 32
padding = (0, pw - w, 0, ph - h)
fourcc = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
tot_frame = videoCapture.get(cv2.CAP_PROP_FRAME_COUNT)
print('{}.mp4, {} frames in total, {}FPS to {}FPS'.format(args.video[:-4], tot_frame, fps, 4*fps))
pbar = tqdm(total=tot_frame)
if args.montage:
    output = cv2.VideoWriter('{}_4x.mp4'.format(args.video[:-4]), fourcc, fps*4, (2*w, h))
else:        
    output = cv2.VideoWriter('{}_4x.mp4'.format(args.video[:-4]), fourcc, fps*4, (w, h))
frame = frame
while success:
    lastframe = frame
    success, frame = videoCapture.read()
    if success:
        I0 = torch.from_numpy(np.transpose(lastframe, (2,0,1)).astype("float32") / 255.).to(device).unsqueeze(0)
        I1 = torch.from_numpy(np.transpose(frame, (2,0,1)).astype("float32") / 255.).to(device).unsqueeze(0)
        I0 = F.pad(I0, padding)
        I1 = F.pad(I1, padding)
        if (F.interpolate(I0, (16, 16), mode='bilinear', align_corners=False)
            - F.interpolate(I1, (16, 16), mode='bilinear', align_corners=False)).abs().mean() > 0.2:
            mid0 = lastframe
            mid1 = lastframe
            mid2 = frame
        else:
            mid1 = model.inference(I0, I1)
            mid0 = model.inference(I0, mid1)
            mid2 = model.inference(mid1, I1)
            mid0 = (((mid0[0] * 255.).cpu().detach().numpy().transpose(1, 2, 0))).astype('uint8')
            mid1 = (((mid1[0] * 255.).cpu().detach().numpy().transpose(1, 2, 0))).astype('uint8')
            mid2 = (((mid2[0] * 255.).cpu().detach().numpy().transpose(1, 2, 0))).astype('uint8')
        if args.montage:
            output.write(np.concatenate((lastframe, lastframe), 1))
            output.write(np.concatenate((lastframe, mid0[:h, :w]), 1))
            output.write(np.concatenate((lastframe, mid1[:h, :w]), 1))
            output.write(np.concatenate((lastframe, mid2[:h, :w]), 1))
        else:
            output.write(lastframe)
            output.write(mid0[:h, :w])
            output.write(mid1[:h, :w])
            output.write(mid2[:h, :w])
        pbar.update(1)
if args.montage:
    output.write(np.concatenate((lastframe, lastframe), 1))
else:
    output.write(lastframe)
pbar.close()
output.release()
