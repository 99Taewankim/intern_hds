import os

from pikepdf import Pdf
from pdf2image import convert_from_path
from PIL import Image

from pdb import set_trace as st

# Constants
POPPLER_PATH = "libraries/poppler/Library/bin"


def pdf_to_img(file_path: str, save_dir: str, isMac: bool = False):
    '''
      pdf를 jpg로 저장

      Inputs:
      - file_path: jpg로 저장할 pdf 파일 경로
      - save_dir: 분리한 jpg를 저장할 폴더 경로
      - isMac: 맥북인 경우 POPPLER_PATH 지정 없이 실행

      Returns:
      - (list) 분리한 jpg 파일 경로
    '''
    file_name = file_path[:-4]
    pages = []
    if isMac:
        pdf = convert_from_path(file_path)
    else:
        pdf = convert_from_path(file_path,
                                poppler_path=POPPLER_PATH)

    # 각 페이지 분리
    for i, page in enumerate(pdf):
        # 페이지 JPEG 파일로 저장
        save_path = f"{save_dir}/{file_name}_{i:02d}.jpg" \
            if save_dir and save_dir != ''\
            else f"{file_name}_{i:02d}.jpg"
        page.save(save_path, "JPEG")
        pages.append(save_path)

    return pages


def shrink_file2(origPath: str, savePath: str, maxSize: int | float, isMac: bool = False, minQuality=50):
    '''
        파일 용량 압축
        Inputs:
            - origPath: (str) 압축할 파일의 경로
            - savePath: (str) 저장할 경로
            - maxSize:  (int or float) 최대 용량(KB)
        Returns:
            (bool) 압축 성공 여부
    '''
    # 파일 확장자 확인
    fileType = origPath.split(".")[-1].lower()

    # 확장자별 파일 압축
    if fileType == "pdf":
        return shrink_pdf2(origPath, savePath, maxSize, isMac, minQuality=minQuality)

    elif fileType in ["jpg", "jpeg", "png"]:
        return savePath if shrink_img2(origPath, savePath, maxSize, minQuality=minQuality) else None

    else:
        # 압축 불가능한 확장자 -> 압축 실패 처리
        return None


def shrink_pdf2(origPath: str, savePath: str, maxSize: int | float, isMac: bool = False, minQuality=50):
    '''
        pdf 용량 압축(A4 사이즈)
        Inputs:
            - origPath: (str) 압축할 파일의 경로
            - savePath: (str) 저장할 경로
            - maxSize:  (int or float) 최대 용량(KB)
        Returns:
            (bool) 압축 성공 여부
    '''
    try:
        # pdf 각 페이지를 이미지로 나누기
        tmpName = origPath[:-4]
        pages = []
        if isMac:
            pdf = convert_from_path(origPath)
        else:
            pdf = convert_from_path(origPath,
                                    poppler_path=POPPLER_PATH)

        # 각 페이지 분리
        for i, page in enumerate(pdf):
            # 페이지 JPEG 파일로 저장
            origPage = f"{tmpName}_{i:02d}.jpg"
            savedPage = f"{tmpName}_compressed_{i:02d}.jpg"
            pdf[i].save(origPage, "JPEG")

            # 분리된 페이지 압축
            tmp_maxSize = (os.path.getsize(origPage) / 1024) * 0.5
            compressed: bool = shrink_img2(origPage, savedPage, tmp_maxSize)
            pages.append(savedPage)

        # 페이지별 압축
        shrinked = []
        for page in pages:
            shrink_img2(origPath, savePath, maxSize,
                        minQuality=minQuality)  # 90%로 1회 압축
            shrinked.append(Image.open(page).convert('RGB'))

        # 압축된 페이지 pdf로 묶기
        img_start = shrinked[0]
        del shrinked[0]
        img_start.save(
            savePath,
            save_all=True,
            append_images=shrinked,
            allow_overwriting_input=True
        )

        return savePath

    except:
        return None


def shrink_img2(origPath: str, savePath: str, maxSize: int | float, minQuality=45):
    '''
        A4 사이즈로 이미지 용량 압축(jpg, jpeg, png)
        Inputs:
            - origPath: (str) 압축할 파일의 경로
            - savePath: (str) 저장할 경로
            - maxSize:  (int or float) 최대 용량(KB)
        Returns:
            (bool) 압축 성공 여부
    '''

    done = False

    try:
        # 파일 열기
        img = Image.open(origPath).convert("RGB").resize(
            (595, 842), resample=Image.Resampling.LANCZOS)

        # 용량 압축
        quality = 90
        while ((not done) and (quality >= minQuality)):
            # 용량 압축
            img.save(savePath, "JPEG", quality=quality, dpi=(72, 72))

            # 압축된 용량 확인
            fileSize = os.path.getsize(savePath) / 1024
            if fileSize > maxSize:
                # 최대 용량 이상인 경우 -> 재압축
                quality -= 1
            else:
                # 최대 용량 이내인 경우 -> 압축 멈춤
                done = True
    except:
        done = False

    # 성공 여부 리턴
    return True if done else False
