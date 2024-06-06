#!/usr/bin/env python
# coding: utf-8

# In[ ]:


from libraries.hirevisa.download2 import download_file_from_airtable as download
from libraries.hirevisa.file import pdf_to_img
from libraries.hirevisa.dormitory_gpt import *
from libraries.hirevisa.others_gpt import *
from libraries.hirevisa.utils import clear_dir
from pyairtable import Table        # 에어테이블
import os
import re
from time import sleep
from tqdm import tqdm
from traceback import format_exc
from pdb import set_trace as st

# ----------- 👇👇👇 수정 필요 👇👇👇 -----------
info = {
    '모드': {
        '맥북': False,
    },
    'token': 'airtalbetoken',
    'base': 'airtablebase',
    'table': '신규 업무 처리',
    'view': '주소 입력 뷰',
    '칼럼명': {
        '거주지서류' : '8. 오프라인 서류',
        '주소': '주소',
    }
}
# ----------- 👆👆👆 수정 필요 👆👆👆 -----------

DIRS = {
    '다운로드': 'downloads',
}
MAX_COUNT = 10

#기숙사 서류 용도
def make_addr(
    user: dict,
) -> dict:
    '''
        거주지 OCR
    '''
    # 거주지 서류 다운로드
    clear_dir(DIRS['다운로드'])
    file_names = download(
        user['fields'][info['칼럼명']['거주지서류']],
        DIRS['다운로드'],
        user['id'],
    )
    file_path = file_names[-1]
    file_name = file_path.split('/')[-1]
    file_type = file_path.split('.')[-1].lower()

    count = 0
    while count < MAX_COUNT and file_name not in os.listdir(DIRS['다운로드']):
        sleep(1)

    if file_name not in os.listdir(DIRS['다운로드']):
        print(f'- {user["id"]}: 파일 다운로드 실패')

    if file_type == 'pdf':
        # pdf 파일일 경우 이미지 파일로 쪼개기
        file_path = pdf_to_img(
            file_path,
            '',
            info['모드']['맥북']
        )[0]

    #거주지 서류 OCR
    addr = return_addr(file_path)

    return {
        info['칼럼명']["주소"]: addr,
    }

#나머지 서류 용도
def make_addr2(
    user: dict,
) -> dict:
    '''
        거주지 OCR
    '''
    # 거주지 서류 다운로드
    clear_dir(DIRS['다운로드'])
    file_names = download(
        user['fields'][info['칼럼명']['거주지서류']],
        DIRS['다운로드'],
        user['id'],
    )

    count = 0

    #여러개 파일 ocr 필요하다.
    #path가 여러개이므로 여기서부터 수정이 필요하다.
    doc_ocr=""
    sub_ocr=""
    sub_ocr2=""
    sub_ocr3=""
    for path in file_names:
        file_name = path.split('/')[-1]
        file_type = path.split('.')[-1].lower()
        while count < MAX_COUNT and file_name not in os.listdir(DIRS['다운로드']):
            sleep(1)
        # pdf 파일일 경우 이미지 파일로 쪼개기
        if file_type == 'pdf':
            path = pdf_to_img(
                path,
                '',
                info['모드']['맥북']
            )
            for img_file_path in path:
                a,b,c,d=extract_text(img_file_path)
                if a!="":
                    doc_ocr=doc_ocr+a+"\nocr 페이지 구분용 텍스트입니다.\n"
                if b!="":
                    sub_ocr=sub_ocr+b+"\nocr 페이지 구분용 텍스트입니다.\n"
                if c!="":
                    sub_ocr2=sub_ocr2+c+"\nocr 페이지 구분용 텍스트입니다.\n"
                if d!="":
                    sub_ocr3=sub_ocr3+d+"\nocr 페이지 구분용 텍스트입니다.\n"
        else:
            a,b,c,d=extract_text(path)
            if a!="":
                doc_ocr=doc_ocr+a+"\nocr 페이지 구분용 텍스트입니다.\n"
            if b!="":
                sub_ocr=sub_ocr+b+"\nocr 페이지 구분용 텍스트입니다.\n"
            if c!="":
                sub_ocr2=sub_ocr2+c+"\nocr 페이지 구분용 텍스트입니다.\n"
            if d!="":
                sub_ocr3=sub_ocr3+d+"\nocr 페이지 구분용 텍스트입니다.\n"

    return doc_ocr,sub_ocr,sub_ocr2,sub_ocr3

if __name__ == '__main__':
    table = Table(
        info['token'],
        info['base'],
        info['table']
    )
    users = table.all(view=info['view'])

    for user in tqdm(users):
        # 거주지 서류 존재 여부 확인
        if info['칼럼명']['거주지서류'] not in user['fields']:
            print(f'- {user["id"]}: 거주지서류 없음')
            continue

        # 거주지 OCR시작
        data = ""
        #기숙사 서류인 경우
        if user['fields']['거주형태']=='학교 기숙사':
            try:
                data = make_addr(user)
            except:
                #한번만 더 시도
                try:
                    data = make_addr(user)
                except:
                    print(f'- {user["id"]}: OCR 도중 실패')
                    continue
         
            try:
                table.update(user["id"], data)
            except:
                error_raw = format_exc()
                format_error = re.compile(
                    r"(?<=\\'message\\': \\').*(?=\\'})"
                )
                error = format_error.search(error_raw)
                error_msg = error.group() if error else '-'

                print(f'- {user["id"]}: 결과 업로드 실패 / Error: {error_msg}')
        
        #기숙사 서류가 아닌 경우
        else:
        #데이터 가져오기
            try:
                a,b,c,d= make_addr2(user)
                # print(a,end="\n메인 텍스트 입니다.\n")
                # print(b,end="\n서브 텍스트 입니다.\n")
                # print(c,end="\n호실 텍스트 입니다.\n")
                # print(d,end="\n사업자등록증 텍스트 입니다.\n")
                data=remove_bracketed_text(gpt_extract_addr(a,b,c,d))
                data = {info['칼럼명']["주소"]: data}
            except:
                #한번만 더 시도
                try:
                    a,b,c,d= make_addr2(user)
                    data=remove_bracketed_text(gpt_extract_addr(a,b,c,d))
                    data = {info['칼럼명']["주소"]: data}
                except:
                    print(f'- {user["id"]}: OCR 도중 실패')
                    continue
            try:
                table.update(user["id"], data)
            except:
                error_raw = format_exc()
                format_error = re.compile(
                    r"(?<=\\'message\\': \\').*(?=\\'})"
                )
                error = format_error.search(error_raw)
                error_msg = error.group() if error else '-'

                print(f'- {user["id"]}: 결과 업로드 실패 / Error: {error_msg}')

