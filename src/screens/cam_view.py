import cv2
import numpy as np
import pygame
import mediapipe as mp

mp_drawing = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles
mp_hands = mp.solutions.hands

def _rgb_to_surface(frame_rgb):
    # pygame.surfarray expects array shape (width, height, 3)
    return pygame.surfarray.make_surface(np.transpose(frame_rgb, (1, 0, 2)))

def _bgr_to_surface(frame_bgr, size):
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    frame_rgb = cv2.resize(frame_rgb, size, interpolation=cv2.INTER_LINEAR)
    return _rgb_to_surface(frame_rgb)

def render_single_camera(surface, frame_bgr, hands_obs, area_rect):
    if frame_bgr is None:
        return
    x, y, w, h = area_rect
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    frame_rgb = _fit_crop(frame_rgb, w, h)
    frame_bgr2 = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

    # draw all hands on same image
    for ho in hands_obs:
        if (not ho.present) or (ho.landmarks is None):
            continue
        mp_drawing.draw_landmarks(
            frame_bgr2, ho.landmarks, mp_hands.HAND_CONNECTIONS,
            mp_styles.get_default_hand_landmarks_style(),
            mp_styles.get_default_hand_connections_style(),
        )

    # frame_rgb is already cropped/resized; draw landmarks were on frame_bgr2
    frame_rgb2 = cv2.cvtColor(frame_bgr2, cv2.COLOR_BGR2RGB)
    surface.blit(_rgb_to_surface(frame_rgb2), (x, y))

def render_two_cameras(surface, left_frame, left_hands, right_frame, right_hands, area_rect):
    """Render two independent camera feeds into left/right halves."""
    x, y, w, h = area_rect
    half_w = w // 2

    # left
    if left_frame is not None:
        l = left_frame.copy()
        for ho in left_hands:
            if (not ho.present) or (ho.landmarks is None):
                continue
            mp_drawing.draw_landmarks(
                l, ho.landmarks, mp_hands.HAND_CONNECTIONS,
                mp_styles.get_default_hand_landmarks_style(),
                mp_styles.get_default_hand_connections_style(),
            )
        lrgb = cv2.cvtColor(l, cv2.COLOR_BGR2RGB)
        lrgb = _fit_crop(lrgb, half_w, h)
        surface.blit(_rgb_to_surface(lrgb), (x, y))

    # right
    if right_frame is not None:
        r = right_frame.copy()
        for ho in right_hands:
            if (not ho.present) or (ho.landmarks is None):
                continue
            mp_drawing.draw_landmarks(
                r, ho.landmarks, mp_hands.HAND_CONNECTIONS,
                mp_styles.get_default_hand_landmarks_style(),
                mp_styles.get_default_hand_connections_style(),
            )
        rrgb = cv2.cvtColor(r, cv2.COLOR_BGR2RGB)
        rrgb = _fit_crop(rrgb, half_w, h)
        surface.blit(_rgb_to_surface(rrgb), (x + half_w, y))


def _fit_crop(img_rgb, target_w, target_h):
    """Crop center to match target aspect ratio, then resize."""
    h, w = img_rgb.shape[:2]
    if w == 0 or h == 0:
        return img_rgb
    target_ar = target_w / float(target_h)
    src_ar = w / float(h)
    if src_ar > target_ar:
        new_w = int(h * target_ar)
        x0 = max(0, (w - new_w) // 2)
        img_rgb = img_rgb[:, x0:x0+new_w]
    else:
        new_h = int(w / target_ar)
        y0 = max(0, (h - new_h) // 2)
        img_rgb = img_rgb[y0:y0+new_h, :]
    return cv2.resize(img_rgb, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

def render_single_camera_raw(surface, frame_bgr, area_rect, rotate_portrait=True):
    if frame_bgr is None:
        return
    x, y, w, h = area_rect
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    if rotate_portrait:
        frame_rgb = np.rot90(frame_rgb)
    frame_rgb = _fit_crop(frame_rgb, w, h)
    surface.blit(_rgb_to_surface(frame_rgb), (x, y))

def render_two_cameras_raw(surface, left_frame, right_frame, area_rect, rotate_portrait=True):
    x, y, w, h = area_rect
    half_w = w // 2
    if left_frame is not None:
        lrgb = cv2.cvtColor(left_frame, cv2.COLOR_BGR2RGB)
        if rotate_portrait:
            lrgb = np.rot90(lrgb)
        lrgb = _fit_crop(lrgb, half_w, h)
        surface.blit(_rgb_to_surface(lrgb), (x, y))
    if right_frame is not None:
        rrgb = cv2.cvtColor(right_frame, cv2.COLOR_BGR2RGB)
        if rotate_portrait:
            rrgb = np.rot90(rrgb)
        rrgb = _fit_crop(rrgb, half_w, h)
        surface.blit(_rgb_to_surface(rrgb), (x + half_w, y))
