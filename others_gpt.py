from pyairtable import Table        # 에어테이블
import os
import io
import re
from google.cloud import vision
from time import sleep
from tqdm import tqdm
from traceback import format_exc
from pdb import set_trace as st
import openai


def extract_text(file_path: str, MAC=False):
  client = vision.ImageAnnotatorClient()
  with io.open(file_path, 'rb') as image_file:
      content = image_file.read()
  image = vision.Image(content=content)

  response = client.text_detection(image=image)
  texts = response.text_annotations
  persons_list = [{'description': text.description} for text in texts]
  doc_ocr=persons_list[0]['description']
  
  #default setting
  #거주제공확인서
  sub_ocr=""
  #영수증
  sub_ocr2=""
  #사업자등록증
  sub_ocr3=""
  
  #본인 명의 계약 중 6쪽짜리 계약서인 경우
  if "6쪽중" in doc_ocr or "6쪽 중" in doc_ocr:
    if "6쪽중 2쪽" not in doc_ocr and "6쪽 중 2쪽" not in doc_ocr:
      doc_ocr=""
  #계약서로 확인이 불가능할 경우 참고 가능
  elif "거주/숙소제공 확인서" in doc_ocr:
    #문서 중 필요한 부분만 읽어 gpt가 추출하기 용이하게 제공
    try:
      l=doc_ocr.split("\n")[:doc_ocr.split("\n").index('국적')+5]
      sub_ocr='\n'.join(l)
    except:
      try:
        l=doc_ocr.split("\n")[:doc_ocr.split("\n").index('2. 거주/숙소 제공자 (Landlord / Provider )')+5]
        sub_ocr='\n'.join(l)
      except:
        try:
          l=doc_ocr.split("\n")[:doc_ocr.split("\n").index('2. 거주/숙소 제공자 (Landlord / Provider)')+5]
          sub_ocr='\n'.join(l)
        except:
          sub_ocr = doc_ocr
          doc_ocr=""
  #본인명의 계약 type1
  elif '한국공인중개사협회' in doc_ocr or '월세 계약서' in doc_ocr or "월세계약서" in doc_ocr or "전세 계약서" in doc_ocr or "(월세)계약서" in doc_ocr:
    next
  #본인명의 계약 type2
  elif '임대차 계약서' in doc_ocr or '임대차계약서' in doc_ocr:
    next
  #본인명의 계약 type3
  elif 'RENTAL CONTRACT' in doc_ocr:
    next
  #본인명의 계약 type4
  elif 'REAL ESTATE LEASE AGREEMENT' in doc_ocr:
    next
  #Airbnb
  elif 'Payment details' in doc_ocr or '결제 세부정보' in doc_ocr:
    next
  #월세 영수증 정보에서 고시원 호실등을 알 수 있는 경우
  elif 'rent receipt' in doc_ocr.lower() or '월세 영수증' in doc_ocr:
    sub_ocr2 = doc_ocr
    doc_ocr = ""
  elif '사업자등록증' in doc_ocr or '고시원' in doc_ocr or '입실원서' in doc_ocr:
    sub_ocr3 =doc_ocr
    doc_ocr = ""
  else:
    doc_ocr = ""
    
  
  return doc_ocr,sub_ocr,sub_ocr2,sub_ocr3

def gpt_extract_addr(doc_ocr,sub_ocr,sub_ocr2,sub_ocr3):
    api_key = 'gpt_api'
    openai.api_key = api_key

    if doc_ocr!="" and sub_ocr2!="":
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # 사용할 엔진 
            messages=[
                {"role": "system", "content": """ 임대차계약서에서 거주지를 제공받는 사람의 주소 정보를 찾아 한 줄의 한글 주소 형식으로 반환해주세요. 
                제공되는 임대차계약서 데이터는 ocr 텍스트임을 감안해야 하고, 동이나 호실 정보가 있다면 이를 반드시 포함해 주어야 합니다. 
                주소 정보만 바로 데이터베이스에 올릴 예정이니까 다른 추가 텍스트는 절대 덧붙이면 안됩니다. 번역된 주소는 한국 주소 어순에 맞게 반환해야 합니다. 
                추가 ocr 텍스트는 영수증 ocr 데이터로, 해당 데이터에서, 임대차계약서에서 확인할 수 없는 동 또는 호실 정보를 확인할 수 있습니다. 
                ocr 텍스트 정보 및 추가 ocr 텍스트 정보를 모두 고려해서 한 줄의 한글 주소로 반환해주세요.
                주소에는 특별시, 광역시, 도 명을 포함해야 합니다. ocr 텍스트에서 주소 추출이 되지 않으면 '추출실패'를 반환해주세요. 주어진 ocr 텍스트 및 추가 ocr 텍스트는 아래와 같습니다.
                ocr 텍스트 : {}
                추가 ocr 텍스트 : {} """.format(doc_ocr,sub_ocr2)},
                {"role": "user", "content": "{} \n {}".format(doc_ocr,sub_ocr2)}
            ]
        )
    
    elif doc_ocr!="":
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # 사용할 엔진 
            messages=[
                {"role": "system", "content": """ 텍스트에서 서류 제공자가 새로 임대한 주소 정보를 찾아 한 줄의 한글 주소 형식으로 반환해주세요.
                제공되는 데이터는 ocr 텍스트임을 감안해야 하고, 동이나 호실 정보가 있다면 이를 반드시 포함해 주어야 합니다. 
                ocr 데이터 유형은 본인 명의 계약서 혹은 airbnb 결제 페이지입니다.
                'ocr 페이지 구분용 텍스트입니다.'를 통해서 페이지를 구분할 수 있습니다.
                제공된 ocr 데이터 각 페이지에서 맨 처음 나오는 주소지를 반환하면 됩니다. (임차주택의 표시에서 소재지와 임차할 부분 참고)
                 하지만 맨 처음 나오는 주소지가 임차인(Lessor)의 주소가 아닌, 서류를 통해 임대할 예정인 집 주소인지 꼭 확인해야 합니다.
                 본인 명의 계약서인 경우 '1. 부동산의 표시' 부분의 소재지와 임차할 부분을 참고해서 주소를 반환해야 합니다. 이외의 주소는 필요한 주소가 아닙니다.
                 airbnb 결제 페이지의 경우 주소가 영어로 써져 있으므로 한글로 번역해야 합니다.
                페이지가 여러개이더라도, 모두 한 개의 서류 제공자 주소 데이터를 담고 있습니다.
                주소 정보만 바로 데이터베이스에 올릴 예정이니까 다른 추가 텍스트는 절대 덧붙이면 안됩니다. 번역된 주소는 한국 주소 어순에 맞게 반환해야 합니다. 
                특별시, 광역시, 도 명을 포함해야 합니다. ocr 텍스트에서 주소 추출이 되지 않으면 '추출실패'를 반환해주세요. 주어진 ocr 텍스트는 아래와 같습니다.
                ocr 텍스트 : {}""".format(doc_ocr)},
                {"role": "user", "content": "{}".format(doc_ocr)}
            ]
        )
    elif sub_ocr!="" and sub_ocr2!="":
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # 사용할 엔진 
            messages=[
                {"role": "system", "content": """ 거주제공확인서에서 거주지를 제공받는 사람의 주소 정보를 찾아 한 줄의 한글 주소 형식으로 반환해주세요. 
                제공되는 데이터는 ocr 텍스트임을 감안해야 하고, 동이나 호실 정보가 있다면 이를 반드시 포함해 주어야 합니다. 
                '주소(address)'라는 글자 이후, '2. 거주/숙소 제공자' 라는 글자 혹은 '2. 거주/숙소 제공자 (Landlord / Provider )'라는 글자 바로 전후 텍스트에서 주소를 확인할 수 있습니다.
                주소 정보만 바로 데이터베이스에 올릴 예정이니까 다른 추가 텍스트는 절대 덧붙이면 안됩니다. 번역된 주소는 한국 주소 어순에 맞게 반환해야 합니다. 
                추가 ocr 텍스트는 영수증 ocr 데이터로, 해당 데이터에서, 거주제공확인서에서 확인할 수 없는 동 또는 호실 정보를 확인할 수 있습니다. ocr 텍스트 정보 및 추가 ocr 텍스트 정보를 모두 고려해서 한 줄의 한글 주소로 반환해주세요.
                주소에는 특별시, 광역시, 도 명을 포함해야 합니다. ocr 텍스트에서 주소 추출이 되지 않으면 '추출실패'를 반환해주세요. 주어진 ocr 텍스트 및 추가 ocr 텍스트는 아래와 같습니다.
                ocr 텍스트 : {}
                추가 ocr 텍스트 : {} """.format(sub_ocr,sub_ocr2)},
                {"role": "user", "content": "{} \n {}".format(sub_ocr,sub_ocr2)}
            ]
        )
    elif sub_ocr!="":
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # 사용할 엔진 
            messages=[
                {"role": "system", "content": """ 거주제공확인서에서 거주지를 제공받는 사람의 주소 정보를 찾아 한 줄의 한글 주소 형식으로 반환해주세요. 
                제공되는 데이터는 ocr 텍스트임을 감안해야 하고, 동이나 호실 정보가 있다면 이를 반드시 포함해 주어야 합니다. 
                '주소(address)'라는 글자 이후, '2. 거주/숙소 제공자' 라는 글자 혹은 '2. 거주/숙소 제공자 (Landlord / Provider )'라는 글자 바로 전후 텍스트에서 주소를 확인할 수 있습니다.
                주소 정보만 바로 데이터베이스에 올릴 예정이니까 다른 추가 텍스트는 절대 덧붙이면 안됩니다. 번역된 주소는 한국 주소 어순에 맞게 반환해야 합니다. 
                특별시, 광역시, 도 명을 포함해야 합니다. ocr 텍스트에서 주소 추출이 되지 않으면 '추출실패'를 반환해주세요. 주어진 ocr 텍스트는 아래와 같습니다.
                ocr 텍스트 : {}""".format(sub_ocr)},
                {"role": "user", "content": "{}".format(sub_ocr)}
            ]
        )
    elif sub_ocr2!="" and sub_ocr3 !="":
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # 사용할 엔진 
            messages=[
                {"role": "system", "content": """ 사업자 등록증 및 영수증 데이터에서 거주지를 제공받는 사람의 주소 정보를 찾아 한 줄의 한글 주소 형식으로 반환해주세요. 
                제공되는 데이터는 ocr 데이터임을 감안해야 하고, 동이나 호실 정보가 있다면 이를 반드시 포함해 주어야 합니다. 
                주소 정보만 바로 데이터베이스에 올릴 예정이니까 다른 추가 텍스트는 절대 덧붙이면 안됩니다. 번역된 주소는 한국 주소 어순에 맞게 반환해야 합니다. 
                영수증 ocr 데이터에서는 사업자 등록증 ocr 데이터에서 확인할 수 없는 개인의 동 또는 호실 정보를 확인할 수 있습니다. 
                 3자리 혹은 4자리 숫자가 그냥 써져있는 경우도 있습니다. 조금 관대하게 판단해서 추가해주세요.
                 영수증 ocr 데이터의 호실정소까지 주소에 추가해서 한 줄의 한글 주소로 반환해주세요.
                주소에는 특별시, 광역시, 도 명을 포함해야 합니다. ocr 데이터에서 주소 추출이 되지 않으면 '추출실패'를 반환해주세요. 
                 주어진 사업자등록증 ocr 텍스트와 영수증 ocr 텍스트는 아래와 같습니다.
                사업자등록증 ocr 텍스트 : {}
                영수증 ocr 텍스트 : {} """.format(sub_ocr2,sub_ocr3)},
                {"role": "user", "content": "{} \n {}".format(sub_ocr2,sub_ocr3)}
            ]
        )
    elif sub_ocr3!="":
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # 사용할 엔진 
            messages=[
                {"role": "system", "content": """ 사업자 등록증에서 거주지를 제공받는 사람의 주소 정보를 찾아 한 줄의 한글 주소 형식으로 반환해주세요. 
                제공되는 데이터는 ocr 데이터임을 감안해야 하고, 동이나 호실 정보가 있다면 이를 반드시 포함해 주어야 합니다. 
                주소 정보만 바로 데이터베이스에 올릴 예정이니까 다른 추가 텍스트는 절대 덧붙이면 안됩니다. 번역된 주소는 한국 주소 어순에 맞게 반환해야 합니다. 
                주소에는 특별시, 광역시, 도 명을 포함해야 합니다. ocr 데이터에서 주소 추출이 되지 않으면 '추출실패'를 반환해주세요. 
                 주어진 사업자등록증 ocr 텍스트는 아래와 같습니다.
                사업자등록증 ocr 텍스트 : {}""".format(sub_ocr3)},
                {"role": "user", "content": "{}".format(sub_ocr3)}
            ]
        )
    else:
        return ("추출실패")
    
    return response.choices[0].message['content'].strip().replace("'","")

def remove_bracketed_text(address):
    # 괄호 및 대괄호에 있는 내용을 제거하는 정규 표현식 패턴
    pattern = r"\[.*?\]|\(.*?\)"
    # 정규 표현식 패턴을 사용하여 괄호 및 대괄호에 있는 내용을 빈 문자열로 대체
    cleaned_address = re.sub(pattern, '', address)
    # 앞뒤 공백 제거
    cleaned_address = cleaned_address.strip()
    # 여러 공백을 하나의 공백으로 변경
    cleaned_address = re.sub(r'\s+', ' ', cleaned_address)
    return cleaned_address
