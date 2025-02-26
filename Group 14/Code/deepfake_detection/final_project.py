# -*- coding: utf-8 -*-
"""final_project.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1crtm9C0t_YIR9-LTatC6udxx8Zatru0V
"""

# **Frame_Extractor**

import os
import cv2
import numpy as np

class VideoReader:

    def __init__(self, verbose=True, insets=(0, 0)):
        
        self.verbose = verbose
        self.insets = insets

    def read_frames(self, path, num_frames, jitter=0, seed=None):
      # Reads frames that are always evenly spaced throughout the video.
      #     jitter: if not 0, adds small random offsets to the frame indices;
      #         this is useful so we don't always land on even or odd frames
      #     seed: random seed for jittering; if you set this to a fixed value,
      #         you probably want to set it only on the first video 
       
        assert num_frames > 0

        capture = cv2.VideoCapture(path)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count <= 0: return None

        frame_idxs = np.linspace(0, frame_count - 1, num_frames, endpoint=True, dtype=np.int)
        if jitter > 0:
            np.random.seed(seed)
            jitter_offsets = np.random.randint(-jitter, jitter, len(frame_idxs))
            frame_idxs = np.clip(frame_idxs + jitter_offsets, 0, frame_count - 1)

        result = self._read_frames_at_indices(path, capture, frame_idxs)
        capture.release()
        return result

    def read_random_frames(self, path, num_frames, seed=None):
       #Picks the frames at random.
       
        assert num_frames > 0
        np.random.seed(seed)

        capture = cv2.VideoCapture(path)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count <= 0: return None

        frame_idxs = sorted(np.random.choice(np.arange(0, frame_count), num_frames))
        result = self._read_frames_at_indices(path, capture, frame_idxs)

        capture.release()
        return result

    def read_frames_at_indices(self, path, frame_idxs):
      #Reads frames from a video and puts them into a NumPy array
      #Returns:
           # - a NumPy array of shape (num_frames, height, width, 3)
           # - a list of the frame indices that were read
        assert len(frame_idxs) > 0
        capture = cv2.VideoCapture(path)
        result = self._read_frames_at_indices(path, capture, frame_idxs)
        capture.release()
        return result

    def _read_frames_at_indices(self, path, capture, frame_idxs):
      #capture frames at indices for processing
      
        try:
            frames = []
            idxs_read = []
            for frame_idx in range(frame_idxs[0], frame_idxs[-1] + 1):
                # Get the next frame, but don't decode if we're not using it.
                ret = capture.grab()
                if not ret:
                    if self.verbose:
                        print("Error grabbing frame %d from movie %s" % (frame_idx, path))
                    break

                # Need to look at this frame?
                current = len(idxs_read)
                if frame_idx == frame_idxs[current]:
                    ret, frame = capture.retrieve()
                    if not ret or frame is None:
                        if self.verbose:
                            print("Error retrieving frame %d from movie %s" % (frame_idx, path))
                        break

                    frame = self._postprocess_frame(frame)
                    frames.append(frame)
                    idxs_read.append(frame_idx)

            if len(frames) > 0:
                return np.stack(frames), idxs_read
            if self.verbose:
                print("No frames read from movie %s" % path)
            return None
        except:
            if self.verbose:
                print("Exception while reading movie %s" % path)
            return None    

    def read_middle_frame(self, path):
      #Reads the frame from the middle of the video
        
        capture = cv2.VideoCapture(path)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        result = self._read_frame_at_index(path, capture, frame_count // 2)
        capture.release()
        return result

    def read_frame_at_index(self, path, frame_idx):
      #this is the more efficient way to read single frame from a video
        
        capture = cv2.VideoCapture(path)
        result = self._read_frame_at_index(path, capture, frame_idx)
        capture.release()
        return result

    def _read_frame_at_index(self, path, capture, frame_idx):
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = capture.read()    
        if not ret or frame is None:
            if self.verbose:
                print("Error retrieving frame %d from movie %s" % (frame_idx, path))
            return None
        else:
            frame = self._postprocess_frame(frame)
            return np.expand_dims(frame, axis=0), [frame_idx]
    
    def _postprocess_frame(self, frame):
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if self.insets[0] > 0:
            W = frame.shape[1]
            p = int(W * self.insets[0])
            frame = frame[:, p:-p, :]

        if self.insets[1] > 0:
            H = frame.shape[1]
            q = int(H * self.insets[1])
            frame = frame[q:-q, :, :]

        return frame

# **FaceExtractor**



import os
import cv2
import numpy as np
import torch


class FaceExtractor:
    
    def __init__(self, video_read_fn, facedet):
      # video_read_fn: a function that takes in a path to a video file
      #           and returns a tuple consisting of a NumPy array with shape
      #           (num_frames, H, W, 3) and a list of frame indices, or None
      #           in case of an error
      #       facedet: the face detector object
       
        self.video_read_fn = video_read_fn
        self.facedet = facedet
    
    def process_videos(self, input_dir, filenames, video_idxs):
      # For the specified selection of videos, grabs one or more frames 
      #   from each video, runs the face detector, and tries to find the faces 
      #   in each frame.
        
        target_size = self.facedet.input_size
        videos_read = []
        frames_read = []
        frames = []
        tiles = []
        resize_info = []

        for video_idx in video_idxs:
            # Read the full-size frames from this video.
            filename = filenames[video_idx]
            video_path = os.path.join(input_dir, filename)
            result = self.video_read_fn(video_path)

            
            if result is None: continue

            videos_read.append(video_idx)

           # Keep track of the original frames (need them later).
            my_frames, my_idxs = result
            frames.append(my_frames)
            frames_read.append(my_idxs)
           # Split the frames into several tiles. Resize the tiles to 128x128
            my_tiles, my_resize_info = self._tile_frames(my_frames, target_size)
            tiles.append(my_tiles)
            resize_info.append(my_resize_info)
            # Put all the tiles for all the frames from all the videos into
             # a single batch.

        batch = np.concatenate(tiles)
        # Run the face detector. The result is a list of PyTorch tensors, 
        # one for each image in the batch.
        all_detections = self.facedet.predict_on_batch(batch, apply_nms=False)

        result = []
        offs = 0
        for v in range(len(tiles)):
            num_tiles = tiles[v].shape[0]
            detections = all_detections[offs:offs + num_tiles]
            offs += num_tiles
            detections = self._resize_detections(detections, target_size, resize_info[v])
            # Because we have several tiles for each frame, combine the predictions
            # from these tiles. The result is a list of PyTorch tensors,
            num_frames = frames[v].shape[0]
            frame_size = (frames[v].shape[2], frames[v].shape[1])
            detections = self._untile_detections(num_frames, frame_size, detections)
            # The same face may have been detected in multiple tiles, so filter out
            # overlapping detections. This is done separately for each frame.
            detections = self.facedet.nms(detections)

            for i in range(len(detections)):
               # Crop the faces out of  frame
                faces = self._add_margin_to_detections(detections[i], frame_size, 0.2)
                faces = self._crop_faces(frames[v][i], faces)
                # Add additional information about the frame and detections
                scores = list(detections[i][:, 16].cpu().numpy())
                frame_dict = { "video_idx": videos_read[v],
                               "frame_idx": frames_read[v][i],
                               "frame_w": frame_size[0],
                               "frame_h": frame_size[1],
                               "faces": faces, 
                               "scores": scores }
                result.append(frame_dict)               

        return result

    def process_video(self, video_path):
      #efficient method for doing face extraction on a single video
        input_dir = os.path.dirname(video_path)
        filenames = [ os.path.basename(video_path) ]
        return self.process_videos(input_dir, filenames, [0])

    def _tile_frames(self, frames, target_size):
      # Splits each frame into several smaller, partially overlapping tiles
      #   and resizes each tile to target_size
       
        num_frames, H, W, _ = frames.shape
        split_size = min(H, W)
        x_step = (W - split_size) // 2
        y_step = (H - split_size) // 2
        num_v = 1
        num_h = 3 if W > H else 1

        splits = np.zeros((num_frames * num_v * num_h, target_size[1], target_size[0], 3), dtype=np.uint8)

        i = 0
        for f in range(num_frames):
            y = 0
            for v in range(num_v):
                x = 0
                for h in range(num_h):
                    crop = frames[f, y:y+split_size, x:x+split_size, :]
                    splits[i] = cv2.resize(crop, target_size, interpolation=cv2.INTER_AREA)
                    x += x_step
                    i += 1
                y += y_step

        resize_info = [split_size / target_size[0], split_size / target_size[1], 0, 0]
        return splits, resize_info

    def _resize_detections(self, detections, target_size, resize_info):       
        projected = []
        target_w, target_h = target_size
        scale_w, scale_h, offset_x, offset_y = resize_info

        for i in range(len(detections)):
            detection = detections[i].clone()          
            for k in range(2):
                detection[:, k*2    ] = (detection[:, k*2    ] * target_h - offset_y) * scale_h
                detection[:, k*2 + 1] = (detection[:, k*2 + 1] * target_w - offset_x) * scale_w

            # keypoints are x,y
            for k in range(2, 8):
                detection[:, k*2    ] = (detection[:, k*2    ] * target_w - offset_x) * scale_w
                detection[:, k*2 + 1] = (detection[:, k*2 + 1] * target_h - offset_y) * scale_h

            projected.append(detection)

        return projected    
    
    def _untile_detections(self, num_frames, frame_size, detections):
      # With N tiles per frame, there also are N times as many detections.
      #   This function groups together the detections for a given frame; it is
      #   the complement to tile_frames().
       
        combined_detections = []
        W, H = frame_size
        split_size = min(H, W)
        x_step = (W - split_size) // 2
        y_step = (H - split_size) // 2
        num_v = 1
        num_h = 3 if W > H else 1

        i = 0
        for f in range(num_frames):
            detections_for_frame = []
            y = 0
            for v in range(num_v):
                x = 0
                for h in range(num_h):
                    detection = detections[i].clone()
                    if detection.shape[0] > 0:
                        for k in range(2):
                            detection[:, k*2    ] += y
                            detection[:, k*2 + 1] += x
                        for k in range(2, 8):
                            detection[:, k*2    ] += x
                            detection[:, k*2 + 1] += y

                    detections_for_frame.append(detection)
                    x += x_step
                    i += 1
                y += y_step

            combined_detections.append(torch.cat(detections_for_frame))

        return combined_detections
    
    def _add_margin_to_detections(self, detections, frame_size, margin=0.2):
      #Expands the face bounding box
      #The face detections often do not include the forehead, which
      # is why we use twice the margin for ymin.
      # Returns a PyTorch tensor of shape (num_detections, 17)
        
        offset = torch.round(margin * (detections[:, 2] - detections[:, 0]))
        detections = detections.clone()
        detections[:, 0] = torch.clamp(detections[:, 0] - offset*2, min=0)            # ymin
        detections[:, 1] = torch.clamp(detections[:, 1] - offset, min=0)              # xmin
        detections[:, 2] = torch.clamp(detections[:, 2] + offset, max=frame_size[1])  # ymax
        detections[:, 3] = torch.clamp(detections[:, 3] + offset, max=frame_size[0])  # xmax
        return detections
    
    def _crop_faces(self, frame, detections):
      # Copies the face region(s) from the given frame into a set
        # of new NumPy arrays
        
        faces = []
        for i in range(len(detections)):
            ymin, xmin, ymax, xmax = detections[i, :4].cpu().numpy().astype(np.int)
            face = frame[ymin:ymax, xmin:xmax, :]
            faces.append(face)
        return faces

    def remove_large_crops(self, crops, pct=0.1):
      # Removes faces from the results if they take up more than X% 
        # of the video. Such a face is likely a false positive.
        
        for i in range(len(crops)):
            frame_data = crops[i]
            video_area = frame_data["frame_w"] * frame_data["frame_h"]
            faces = frame_data["faces"]
            scores = frame_data["scores"]
            new_faces = []
            new_scores = []
            for j in range(len(faces)):
                face = faces[j]
                face_H, face_W, _ = face.shape
                face_area = face_H * face_W
                if face_area / video_area < 0.1:
                    new_faces.append(face)
                    new_scores.append(scores[j])
            frame_data["faces"] = new_faces
            frame_data["scores"] = new_scores

    def keep_only_best_face(self, crops):
        
        for i in range(len(crops)):
            frame_data = crops[i]
            if len(frame_data["faces"]) > 0:
                frame_data["faces"] = frame_data["faces"][:1]
                frame_data["scores"] = frame_data["scores"][:1]

# Commented out IPython magic to ensure Python compatibility.
# **Detection**

# !pip install pytorchcv
import os, sys, time
import cv2
import numpy as np
import pandas as pd

import torch
import torch.nn as nn
import torch.nn.functional as F

# %matplotlib inline
import matplotlib.pyplot as plt

import warnings
warnings.filterwarnings("ignore")

!pip install /content/drive/MyDrive/deepfake/xception/pytorchcv-0.0.55-py2.py3-none-any.whl

test_dir = "/content/drive/MyDrive/deepfake/dataset/test_videos"
test_videos = sorted([x for x in os.listdir(test_dir) if x[-4:] == ".mp4"])
frame_h = 5
frame_l = 5
len(test_videos)

gpu = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
gpu

import sys
sys.path.insert(0, "/content/drive/MyDrive/deepfake/blazeface")

from blazeface import BlazeFace
facedet = BlazeFace().to(gpu)
facedet.load_weights("/content/drive/MyDrive/deepfake/blazeface/blazeface.pth")
facedet.load_anchors("/content/drive/MyDrive/deepfake/blazeface/anchors.npy")
_ = facedet.train(False)

frames_per_video = 64 # originally 4

video_reader = VideoReader()
video_read_fn = lambda x: video_reader.read_frames(x, num_frames=frames_per_video)
face_extractor = FaceExtractor(video_read_fn, facedet)

input_size = 150

from torchvision.transforms import Normalize

mean = [0.485, 0.456, 0.406]
std = [0.229, 0.224, 0.225]
normalize_transform = Normalize(mean, std)

def resize_image(img, size, resample=cv2.INTER_AREA):
    h, w = img.shape[:2]
    if w > h:
        h = h * size // w
        w = size
    else:
        w = w * size // h
        h = size

    resized = cv2.resize(img, (w, h), interpolation=resample)
    return resized


def make_square_image(img):
    h, w = img.shape[:2]
    size = max(h, w)
    t = 0
    b = size - h
    l = 0
    r = size - w
    return cv2.copyMakeBorder(img, t, b, l, r, cv2.BORDER_CONSTANT, value=0)

from pytorchcv.model_provider import get_model
model = get_model("xception", pretrained=False)
model = nn.Sequential(*list(model.children())[:-1]) # Remove original output layer

class Pooling(nn.Module):
  def __init__(self):
    super(Pooling, self).__init__()
    
    self.p1 = nn.AdaptiveAvgPool2d((1,1))
    self.p2 = nn.AdaptiveMaxPool2d((1,1))

  def forward(self, x):
    x1 = self.p1(x)
    x2 = self.p2(x)
    return (x1+x2) * 0.5

model[0].final_block.pool = nn.Sequential(nn.AdaptiveAvgPool2d((1,1)))
class Head(torch.nn.Module):
  def __init__(self, in_f, out_f):
    super(Head, self).__init__()
    
    self.f = nn.Flatten()
    self.l = nn.Linear(in_f, 512)
    self.d = nn.Dropout(0.5)
    self.o = nn.Linear(512, out_f)
    self.b1 = nn.BatchNorm1d(in_f)
    self.b2 = nn.BatchNorm1d(512)
    self.r = nn.ReLU()

  def forward(self, x):
    x = self.f(x)
    x = self.b1(x)
    x = self.d(x)

    x = self.l(x)
    x = self.r(x)
    x = self.b2(x)
    x = self.d(x)

    out = self.o(x)
    return out

class FCN(torch.nn.Module):
  def __init__(self, base, in_f):
    super(FCN, self).__init__()
    self.base = base
    self.h1 = Head(in_f, 1)
  
  def forward(self, x):
    x = self.base(x)
    return self.h1(x)

net = []
model = FCN(model, 2048)
model = model.cuda()
model.load_state_dict(torch.load('/content/drive/MyDrive/deepfake/xception/model_50epochs_lr0001_patience5_factor01_batchsize32.pth')) # new, updated
net.append(model)

def predict_on_video(video_path, batch_size):
    try:
        # Find the faces for N frames in the video.
        faces = face_extractor.process_video(video_path)

        # Only look at one face per frame.
        face_extractor.keep_only_best_face(faces)
        
        if len(faces) > 0:
            # NOTE: When running on the CPU, the batch size must be fixed
            # or else memory usage will blow up. (Bug in PyTorch?)
            x = np.zeros((batch_size, input_size, input_size, 3), dtype=np.uint8)

            # If we found any faces, prepare them for the model.
            n = 0
            for frame_data in faces:
                for face in frame_data["faces"]:
                    # Resize to the model's required input size.
                    # We keep the aspect ratio intact and add zero
                    # padding if necessary.                    
                    resized_face = resize_image(face, input_size)
                    resized_face = make_square_image(resized_face)

                    if n < batch_size:
                        x[n] = resized_face
                        n += 1
                    else:
                        print("WARNING: have %d faces but batch size is %d" % (n, batch_size))
                    
                    # Test time augmentation: horizontal flips.
                    # TODO: not sure yet if this helps or not
                    #x[n] = cv2.flip(resized_face, 1)
                    #n += 1

            if n > 0:
                x = torch.tensor(x, device=gpu).float()

                # Preprocess the images.
                x = x.permute((0, 3, 1, 2))

                for i in range(len(x)):
                    x[i] = normalize_transform(x[i] / 255.)
#                     x[i] = x[i] / 255.

                # Make a prediction, then take the average.
                with torch.no_grad():
                    y_pred = model(x)
                    y_pred = torch.sigmoid(y_pred.squeeze())
                    return y_pred[:n].mean().item()

    except Exception as e:
        print("Prediction error on video %s: %s" % (video_path, str(e)))

    return 0.5

from concurrent.futures import ThreadPoolExecutor

def predict_on_video_set(videos, num_workers):
    def process_file(i):
        filename = videos[i]
        y_pred = predict_on_video(os.path.join(test_dir, filename), batch_size=frames_per_video)
        return y_pred

    with ThreadPoolExecutor(max_workers=num_workers) as ex:
        predictions = ex.map(process_file, range(len(videos)))

    return list(predictions)

model.eval()
predictions = predict_on_video_set(test_videos, num_workers=4)

prediction_value = []
for value in predictions:
    if value > .60:
        prediction_value.append('FAKE')
    else:
        prediction_value.append('REAL')

submission_df_xception = pd.DataFrame({"filename": test_videos, "label": predictions,"result":prediction_value})
submission_df_xception.to_csv("/content/drive/MyDrive/deepfake/output/result.csv", index=False)

submission_df_xception.head()