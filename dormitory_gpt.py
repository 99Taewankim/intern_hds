#!/usr/bin/env python
# coding: utf-8

# In[1]:


import os
import io
import re
from PIL import Image
from google.cloud import vision
import json
import openai
import google.generativeai as genai
from pdb import set_trace as st

# Constants
#거주지 서류
MAX_HEIGHT_GAP = 0.05   # 같은 줄로 인식하는 최대 높이(이미지 크기 대비 배율)
MAX_WIDTH_GAP = 0.05    # 같은 줄로 인식하는 최대 너비(이미지 크기 대비 배율)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "./certs/visaocr.json"


# In[2]:


def dorm_to_addr(file_path: str, MAC=False):
  client = vision.ImageAnnotatorClient()
  with io.open(file_path, 'rb') as image_file:
      content = image_file.read()
  image = vision.Image(content=content)

  response = client.text_detection(image=image)
  texts = response.text_annotations
  persons_list = [{'description': text.description} for text in texts]
  doc_ocr=persons_list[0]['description']
  return doc_ocr


# In[3]:


def find_by_pattern_oneline(text):
    pattern = r"((서울(특별)?시|인천(광역)?시|대구(광역)?시|대전(광역)?시|광주(광역)?시|울산(광역)?시|경기도|서울\s*([\uAC00-\uD7A3]{1,5}구))[^\n]*\n)"
    try:
        res=re.search(pattern, text).group(1)
        res=res.replace("\n", "")
        res=re.sub(r'\s+', ' ', res)
        return res
    except:
        return ""


# In[4]:


def find_by_pattern_twoline(text):
    pattern = r"((서울(특별)?시|인천(광역)?시|대구(광역)?시|대전(광역)?시|광주(광역)?시|울산(광역)?시|경기도|서울\s*([\uAC00-\uD7A3]{1,5}구))[^\n]*\n(.*?)\n)"
    try:
        res=re.search(pattern, text).group(1)
        res=res.replace("\n", " ")
        res=re.sub(r'\s+', ' ', res)
        return res
    except:
        return ""


# In[5]:


def find_by_pattern_threeline(text):
    pattern = r"((서울(특별)?시|인천(광역)?시|대구(광역)?시|대전(광역)?시|광주(광역)?시|울산(광역)?시|경기도|서울\s*([\uAC00-\uD7A3]{1,5}구))[^\n]*\n(.*?)\n(.*?)\n)"
    try:
        res=re.search(pattern, text).group(1)
        res=res.replace("\n", " ")
        res=re.sub(r'\s+', ' ', res)
        return res
    except:
        return ""


# In[6]:


def clean_text(cleaned_text, 영어=True, 한자=True, 괄호 = True, 기타 =True):
    if 영어:
        cleaned_text = re.sub(r'[a-zA-Z]+', '', cleaned_text)  # 영어 삭제
    if 한자:
        cleaned_text = re.sub(r'[\u4e00-\u9fff]+', '', cleaned_text)  # 한자 삭제
    if 괄호:
        cleaned_text = re.sub(r'\([^)]*\)', '', cleaned_text)  # 괄호 안의 내용 삭제
    if 기타:
        cleaned_text = cleaned_text.replace(".", "")
        cleaned_text = cleaned_text.replace("\n", "")
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    
    return cleaned_text.strip()


# In[7]:


def gemini_addr(doc_ocr, order_text):
    if doc_ocr == "":
        return None
    genai.configure(api_key="gemini_api")
    model = genai.GenerativeModel('gemini-pro')
    

    text="""
    ocr 텍스트에서 주소 정보를 찾아 한 줄의 한글 주소 형식으로 반환해 주세요. 반환값의 처음 단어는 샘플 주소 형식 첫 단어와 같아야 합니다.
    샘플 주소 형식에 있는 "숫자(0), 문자(O)"정보는 ocr 텍스트 데이터에 있는 정보를 기반으로 수정해서 입력해주세요.
    수정이 필요없는 부분의 반환값은 샘플의 형식과 동일하게 유지해 주세요.
    추출할 샘플 주소 형식 : {}
    ocr 텍스트 :  '{}'
        """.format(order_text, doc_ocr)
    response = model.generate_content(text)
    try:
        addr = response.text
        addr= clean_text(addr,False,False,True,True)
        return addr
    except:
        return None
    
def gemini_subinfo(doc_ocr, order_text):
    if doc_ocr == "":
        return None
    genai.configure(api_key="gemini_api")
    model = genai.GenerativeModel('gemini-pro')
    text="""
    ocr 데이터에서 샘플의 형식에 맞는 "숫자(0), 문자(O)"정보를 찾아 넣어 주세요.
    {}
    ocr 데이터 :  '{}'
    """.format(order_text, doc_ocr)
    response = model.generate_content(text)
    try:
        return response.text.replace("/n","").replace("'","")
    except:
        return None
    
def gpt_trans(doc_ocr):
    api_key = 'gpt_api'
    openai.api_key = api_key
    response = openai.ChatCompletion.create(
        model="gpt-4o",  # 사용할 엔진 
        messages=[
            {"role": "system", "content": """ 텍스트에서 영어로 적힌 주소 정보를 찾아 한 줄의 한글 주소 형식으로 반환해주세요. 제공되는 데이터는 ocr 텍스트임을 감안해야 하고, 기숙사 동이나 호실 정보가 있다면
             이를 반드시 포함해 주어야 합니다. 주소 정보만 바로 데이터베이스에 올릴 예정이니까 다른 추가 텍스트는 절대 덧붙이면 안됩니다. 번역된 주소는 한국 주소 어순에 맞게 반환해야 합니다. 특별시, 광역시,
             도 명을 포함해야 합니다. ocr 텍스트에서 주소 추출이 되지 않으면 '에러'를 반환해주세요. 주어진 ocr 텍스트는 아래와 같습니다.
            ocr 텍스트 : {}""".format(doc_ocr)},
            {"role": "user", "content": "{}".format(doc_ocr)}
        ]
    )
    return response.choices[0].message['content'].strip().replace("'","")

        
def gemini_room(doc_ocr):
    if doc_ocr == "":
        return None
    else:
        genai.configure(api_key="gemini_api")
        model = genai.GenerativeModel('gemini-pro')
        text="""
        텍스트에서 호수 정보를 찾아 3자리 혹은 4자리 숫자로 반환해주세요.
        텍스트에 있는 호수 정보는 'Room' 혹은 '호실' 단어 주변에서 찾을 수 있습니다.
        텍스트 : {}
        """.format(doc_ocr)
        response = model.generate_content(text)
        try:
            if len(response.text)>10:
                return None
            #예외처리 포함하여 리턴
            else:
                return response.text.replace("O","0")
        except:
            return None
        
def gpt_exception(doc_ocr):
    api_key = 'gpt_api'
    openai.api_key = api_key
    response = openai.ChatCompletion.create(
        model="gpt-4o",  # 사용할 엔진 
        messages=[
            {"role": "system", "content": """ 텍스트에서 주소 정보를 찾아 한 줄의 한글 주소 형식으로 반환해주면 돼. 제공되는 데이터는 ocr데이터임을 감안해야 하고, 기숙사 동이나 호실 정보가 있다면
             이를 반드시 포함해 주어야 해. 주소 정보만 바로 데이터베이스에 올릴 예정이니까 다른 추가 텍스트는 절대 덧붙이지 마.
            ocr 텍스트 : {}""".format(doc_ocr)},
            {"role": "user", "content": "{}".format(doc_ocr)}
        ]
    )
    return response.choices[0].message['content'].strip().replace("'","")



#gpt
def ocr_to_gpt_subinfo(ocr,order_text):
    # Set the API key
    api_key = 'gpt_api'
    openai.api_key = api_key
    response = openai.ChatCompletion.create(
        model="gpt-4o",  # 사용할 엔진 
        messages=[
            {"role": "system", "content": """내가 'O'(문자)나 '0'로 비워둔 값들을 예시 샘플로 제시할거고, 너는 ocr 텍스트에서 해당 정보를 찾아서 'O'나 '0' 대신 실제값을 찾아 반환해주면 돼.
             주소 정보에다가 해당정보를 바로 붙일 것이기 때문에, 다른 추가 텍스트는 덧붙이지 마. 반환예시로 들어준 것처럼 작은따옴표 안의 텍스트만 수정해서 반환해줘.
            {}
            ocr 텍스트 : {}""".format(order_text,ocr)},
            {"role": "user", "content": "{}".format(ocr)}
        ]
    )

    return response.choices[0].message['content'].strip()


# In[8]:


def return_addr(path):
    text = dorm_to_addr(path)
    if "중앙대학교" in text:
        order_text = """ocr 텍스트에서 호수 정보를 찾아 '000관 000호' 혹은 '000관 OOO하우스'로 반환해 주세요
                        반환 예시 : 308관 111호, 309관 1111호, 307관 글로벌하우스 """
        info=gemini_subinfo(text,order_text)
        #실패시 재요청
        if "000호" in info or "OOO하우스" in info:
            info=gemini_subinfo(text,order_text)
        text = "서울특별시 동작구 흑석로 84 중앙대학교 "+info

        
    elif "전남대학교" in text:
        order_text = """ocr 텍스트에서 동호실 정보를 찾아 '0O동 0000호' 혹은 '0동 0000호'로 반환해 주세요.
                        동 이름에는 알파벳 대문자 1개 문자가 포함되어 있는 경우가 있습니다.
                        생활실 혹은 동호실 단어 주변에서 해당 정보 확인이 가능합니다.
                        반환 예시 : '7동 1111호' , '8A동 111호'"""             
        info=gemini_subinfo(text,order_text).replace("'","")
        if info[-1]!='호':
            text=""
        else:
            text = '광주광역시 북구 용봉로 77, 전남대학교 생활관 '+info

    elif "조선대학교" in text:
        res = find_by_pattern_oneline(text)
        #주소지 행바꿈으로 인해 잘림 방지
        if res[-1].isdigit():
            text = find_by_pattern_twoline(text) 
        else:
            text = res
        
    elif "동국대학교" in text:
        l=text.split("\n")
        try:
            sublst=l[l.index('구분'):l.index('3. 입사기간(Duration of Stay)')]
            subocr="\n".join(sublst)
            # 층수 정보 추출
            floor = re.search(r'\d', subocr).group(0)  # 첫 번째 숫자 (층수는 1자리)
            room= re.search(r'\d{3,4}', subocr).group(0)  # 호실 3자리 혹은 4자리 숫자

            if "남산학사" in text:
                text = "서울특별시 중구 필동로 1길 30, 남산학사 {}층 {}호".format(floor,room)
            elif "충무학사" in text:
                text = "서울특별시 중구 퇴계로 36길 2, 동국대학교 충무로영상센터 충무학사 {}층 {}호".format(floor,room)
            elif "백상원" in text:
                text = "서울특별시 강북구 화계사길 68 동국대학교 백상원 {}층 {}호".format(floor,room)
        except:
            text = ""
        
    #gpt
    elif "이화여자대학교" in text or "Ewha Womans University" in text:
        order_text = """ocr 텍스트에서 동호실 정보를 찾아 'O하우스 O000호' 혹은 'O하우스 O000-0호'로 반환해 주세요.
                        하우스 이름에는 알파벳 대문자 1개 문자가 포함되어 있어야 합니다.(I 또는 E)
                        호수는 3자리 숫자 혹은 4자리 숫자이며, 호수 바로 앞에있는 알파벳 대문자 하나가 호수 앞 문자에 해당합니다.
                        반환 예시 : OCR 데이터를 보면 'I-House A, B B613' 이런식으로 되어있을 건데, 처음에 나오는 'A, B' 이 부분은 무시하고 'I-House B613' 이렇게 반환하면 돼.
                        기타 반환 예시 : 'E하우스 B111호' , 'I하우스 111-1호' , 'I하우스 A111-1호'
                        """             
        info=ocr_to_gpt_subinfo(text,order_text).replace("'","")
        if info[-1]!='호':
            text=""
        else:
            text = '서울특별시 서대문구 이화여대길 52 이화여자대학교 '+info
        
    elif "가천대학교" in text:
        order_text = "경기도 성남시 수정구 성남대로 1342 제0학생생활관 000호"
        text=gemini_addr(text,order_text)

    elif "홍익대학교" in text:
        order_text = """ocr 텍스트에 기숙사명과 호수를 찾아 '제0기숙사 0000호'으로 반환해 주세요"""
        info=ocr_to_gpt_subinfo(text,order_text).replace("'","")
        text = "서울특별시 마포구 와우산로 94 홍익대학교 "+info


    elif "한국외국어대학교" in text:
        if '글로벌홀' in text:
            order_text = """서울특별시 동대문구 이문로 114 한국외국어대학교 글로벌홀 기숙사 0000O"""
            text=gemini_addr(text,order_text)
            #호실 추출이 잘 안되는 경우 더블체크
            if not 'A'<text[-1]<'Z':
                text=gemini_addr(text,order_text)
        elif '국제학사' in text:
            order_text = "서울시 동대문구 이문로 한국외국어대학교 국제학사 0000호"
            text=gemini_addr(text,order_text)
        else:
            text=find_by_pattern_oneline(text)

   
    elif "한양대학교" in text:
        order_text = """서울특별시 성동구 왕십리로 222, 한양대학교 000관 O-0000호 
                        또는
                        서울특별시 성동구 왕십리로 222, 한양대학교 000사 O-000호"""
        text=gemini_addr(text,order_text)
    
    elif "Hanyang University" in text and "서울특별시" in text:
        text = find_by_pattern_oneline(text)
        
    elif "국민대학교" in text:
        order_text = "서울특별시 성북구 정릉로 77 국민대학교 교내생활관 O동 000호"
        text=gemini_addr(text,order_text)

    #정확도 낮음
    elif "건국대학교" in text:
        order_text = """ocr 텍스트에서 호실 정보를 찾아 3자리 혹은 4자리 숫자로 반환해 주세요.
                        해당 정보는 '홀 / 호실' 주변에서 확인 가능하고, '/'뒤에 숫자로만 기재되어 있습니다.
                        '/' 뒤에 문자가 혼합해서 ocr 되었을 수도 있는데, 이는 워터마크로 인한 것이므로 무시하면 된다.
                        반환예시 : '111' 
                        반환예시 : '1111' 
                        """             
        info=ocr_to_gpt_subinfo(text,order_text).replace("'","")
        if '드림홀' in text:
            text = "서울특별시 광진구 능동로 120 건국대학교 기숙사 드림홀 {}호".format(info)
        elif '비전홀' in text:
            text = "서울특별시 광진구 능동로 120 건국대학교 기숙사 비전홀 {}호".format(info)
        else:
            text ="'"

    elif "고려대학교" in text:
        if "거주/숙소제공 확인서" in text or "거주/숙소제공확인서" in text:
            text = find_by_pattern_oneline(text)
        else:   
            text = find_by_pattern_twoline(text)
            text=text.replace("남자동", "남자동 ")
            text=text.replace("여자동", "여자동 ")

    elif "명지대학교" in text:
        match = re.search(r'사\s*생\s*확\s*인\s*증\s*', text)
        if not match:
            괄호 = False
        else:
            괄호 = True  
        
        res = find_by_pattern_twoline(text)
        res = clean_text(res,괄호=괄호)
        #OCR 예외 처리
        if res[-1]=="•":
            res = find_by_pattern_threeline(text).replace("•","")
        elif '\uac00' <= res[-1] <= '\ud7af':
            res = find_by_pattern_threeline(text)
            res = clean_text(res,괄호=괄호)
        text = res

        #괄호 ocr 인식 못하는 경우 발생(ocr 예외 처리 추가)
        text = text.replace("건물 번호 8번) ","")

  
    elif "서울과학기술대학교" in text:
        order_text = "학사명, 남자동/여자동 여부, 호수정보를 찾아 'OO학사 OOO동 000호' 형식으로 반환해주세요"
        info=gemini_subinfo(text,order_text)
        #gemini 인식 실패시 재요청
        if '000호' in info or "OOO동" in info:
            info=gemini_subinfo(text,order_text)
        text= "서울특별시 노원구 공릉로 58길 130 " + info

    
    #gpt
    elif "성균관대학교" in text:
        l=text.split('\n')
        addr = find_by_pattern_oneline(text)
        if "수원" in addr:
            order_text = """ocr텍스트에서 기숙사명 정보를 찾아 반환해주세요.
                            기숙사명 종류로는'신관A', '신관B', '의관', '예관', '인관'이 있습니다. 영어로 기재되어 있으면 반드시 번역해서 예시 종류처럼 수정 후 반환해주세요.
                            호실정보도 있으면, 호실정보도 '0000호'형태로 반환해주세요. 호실정보는 줄구분되어 '3자리 혹은 4자리 숫자'로 ocr텍스트에 기재되어있습니다.
                            호실정보를 찾을 때, 올해 연도에 해당하는 4자리 숫자는 호실정보가 아니니 호실을 찾을때 배제해주세요.
                            기숙사명이 간혹 기재되어있지 않은 경우가 있는데 이때는 ""로 반환해주세요.
                            호가 있는 경우 반환 예시 :  '신관B동 1111호'
                            호가 없는 경우 반환 예시 : '신관A동'
                            알파벳이 없는 경우 반환 예시 : '의관 1111호'
                            잘못된 반환 예시 : 'Ui관 O동 2066호' -> 영어로 바꾸고, 동이 없으니 생략하고, 주소지에 붙어있는 숫자는 호수가 아니므로 '의관'으로만 반환한다.
                            잘못된 반환 예시 : '신관A동 2024호' -> 올해 년도인 2024년을 호수로 착각한 것이므로 호수 정보를 잘못 기재한 거야. 올바른 호수 정보를 다시 찾아서 반환해야 해."""
            
            #info = gemini_subinfo(text,order_text)
            info = ocr_to_gpt_subinfo(text,order_text).replace("'","")
            text = addr + " " + info

        elif "서울" in addr:
            order_text = """ocr텍스트에서 하우스 명을 찾아 'O-하우스'형태로 반환해주세요.
                            반환 예시 : 'G-하우스', 'M-하우스'"""
            #info = gemini_subinfo(text,order_text)
            info = ocr_to_gpt_subinfo(text,order_text).replace("'","").replace("1-하우스","I-하우스")

            if 'O-하우스' in info:
                info = ocr_to_gpt_subinfo(text,order_text).replace("'","")
            text = addr + " " + info


    #gpt
    #이렇게까지 해도 오기재 할 때가 있다.
    elif "Sungkyunkwan" in text:
        order_text = """ocr텍스트에서 기숙사명 정보를 찾아 반환해주세요.
                기숙사명은 'In-kwan, Ui-kwan, Ye-kwan, Shin-kwan' 중 하나이며, 동은 알파벳 대문자입니다. 한글로 각각 '인관, 의관, 예관, 신관A동, 신관B동'으로 반환하면 됩니다.
                호실정보도 있으면, 호실정보도 '0000호'형태로 반환해주세요. 호실정보는 줄구분되어 '3자리 혹은 4자리 숫자'로 ocr텍스트에 기재되어있습니다.
                호실정보를 찾을 때, 올해 연도에 해당하는 4자리 숫자는 호실정보가 아니니 호실을 찾을때 배제해주세요.
                기숙사명이 간혹 기재되어있지 않은 경우가 있는데 이때는 ""로 반환해주세요.
                호가 있는 경우 반환 예시 :  '신관B동 1111호'
                호가 없는 경우 반환 예시 : '신관A동'
                알파벳이 없는 경우 반환 예시 : '의관 1111호'
                잘못된 반환 예시 : 'Ui관 O동 2066호' -> 영어로 바꾸고, 동이 없으니 생략하고, 주소지에 붙어있는 숫자는 호수가 아니므로 '의관'으로만 반환한다.
                잘못된 반환 예시 : '신관A동 2024호' -> 올해 년도인 2024년을 호수로 착각한 것이므로 호수 정보를 잘못 기재한 거야. 올바른 호수 정보를 다시 찾아서 반환해야 해."""
        info=ocr_to_gpt_subinfo(text,order_text).replace("'","")
        text = "경기도 수원시 장안구 서부로 2066 " + info



    elif "서울대학교 언어교육원" in text:
        text=text.replace("\n","")
        info = None
        if "시흥캠퍼스" in text:
            order_text = """ocr 텍스트에서 호수 정보를 찾아 '000호' 혹은 '0000호'로 반환해 주세요
                            호수 정보는 '시흥캠퍼스 기숙사' 단어 근처에 있습니다. 
                            잘못된 반환 예시 : '0100호' -> 앞자리 0은 생략해서 '100호'로 반환합니다."""
            info=gemini_subinfo(text,order_text)
            if info[-1]!='호':
                text=""
            else:
                text="경기도 시흥시 서울대학로 173 교육연수동 "+info
        elif '우리하우스' in text:
            order_text = """ocr 텍스트에서 호수 정보를 찾아 '000호' 혹은 '0000호'로 반환해 주세요
                        호수 정보는 '우리하우스' 단어 근처에 있습니다. 
                        잘못된 반환 예시 : '0100호' -> 앞자리 0은 생략해서 '100호'로 반환합니다."""
            info=gemini_subinfo(text,order_text)
            if info[-1]!='호':
                text=""
            else:
                text="서울특별시 관악구 복은8길 8-9 우리하우스 "+info
        #gpt
        elif '드래곤' in text:
            order_text = """ocr 텍스트에서 호실명 정보를 찾아 '드래곤O 000호' 혹은 '드래곤O 우리 000호'로 반환해 주세요.
                        호실명에 '우리'가 들어가는 경우가 있기 때문에 반환의 유형을 위처럼 2가지 설정했습니다.
                        '드래곤' 바로 뒤에 들어가는 문자1개는 호실명의 타입을 의미하며, 'B'타입, 'C1'타입 'S'타입, 혹은 타입이 없을수도 있습니다.
                        호수 정보는 '드래곤' 단어 근처에 있습니다.
                        반환예시 : '드래곤B 123호', '드래곤 1209호'이 있습니다.
                        잘못된 반환 예시 : '드래곤 0100호' -> 앞자리 0은 생략해서 '드래곤 100호'로 반환합니다.
                         """
            info=ocr_to_gpt_subinfo(text,order_text).replace("'","").replace('"','')
            if info[-1]!='호':
                text=""
            else:
                if "서림11길" in text:
                    text = "서울특별시 관악구 서림11길 11 "+info
                elif "복은8길" in text:
                    text = "서울특별시 관악구 복은8길 8-9 " +info 
                elif "103-137" in text:
                    text = "서울특별시 관악구 신림동 103-137 "+info
                else:
                    text = ""

        elif "관악사" in text:
            order_text = """ocr 텍스트에 동과 호수를 찾아 '000동 000호'로 반환해 주세요
                            '기숙사 주소 : '뒤에 있는 텍스트에서 찾을 수 있습니다.
                            동과 호수는 각각 3자리 혹은 4자리 숫자입니다. 
                            잘못된 반환 예시 : '0300동 0100호' -> 앞자리 0은 생략해서 '300동 100호'로 반환합니다."""
            info=gemini_subinfo(text,order_text).replace("'","")
            text="서울특별시 관악구 관악로 1 서울대학교 관악사 "+info
        else:
            text=""

    #gpt
    elif "서울대학교" in text or "Gwanak Residence" in text:
        text=text.replace("\n"," ")
        order_text = """ocr 텍스트에 동과 호수를 찾아 '000동 000호 O'으로 반환해 주세요
                ocr 된 결과물 영어 예시 : ocr 데이터에서 '111bldg, 111 A' 가 확인되면 '111동 111호 A'로 반환합니다.
                ocr 된 결과물 한글 예시 : ocr 데이터에서 '222동 222호 A' 가 확인되면 '222동 222호 A'로 반환합니다."""
        info=ocr_to_gpt_subinfo(text,order_text).replace("'","")
        text = "서울특별시 관악구 관악로 1 "+info

    
    elif "서강대학교" in  text:
        text = find_by_pattern_oneline(text)


    elif "숙명여자대학교" in  text or "Sookmyung" in text:
        l=text.split('\n')
        order_text = None
        try:
            text = "서울특별시 용산구 신흥로 26길 20 해방타워, 숙명여대 국제관 "
            room = l[l.index('주소')-1]+"호"
            text += room
        except:
            text= ""


    elif "숭실대학교" in text:
        if "레지던스홀" in text:
            text = "서울특별시 동작구 상도로 369 숭실대학교 생활관 레지던스홀"
        #교외기숙사
        elif "대하빌라" in text:
            room = re.findall(r'(\d+호)',text)
            if room:
                text = "서울특별시 동작구 상도로55길 89 "+room[-1]
            else:
                text = ""
        else:
            text = ""


    elif "서울여자대학교" in text:
        if "국제생활관" in text:
            try:
                room = re.findall(r'(\d+호)',text)[-1]
                text = "서울 노원구 화랑로 621 서울여자대학교 국제생활관 "+room
            except:
                text = ""

        elif "인성교육관" in text:
            text = "서울 노원구 화랑로 621 서울여자대학교 바롬인성교육관"

        elif "국제교육관" in text:
            text = "서울 노원구 화랑로 621 서울여자대학교 국제교육관"

        else:
            text=""

        
    elif "서울시립대학교" in text:
        if "국제학사" in text:
            text = "서울특별시 동대문구 서울시립대로 163 서울시립대학교 국제학사"
        elif "생활관" in text:
            try:
                room = re.search(r'(\d+호)',text).group(1)
            except:
                room = ""
            text = "서울시 동대문구 서울시립대로 163 서울시립대학교 생활관 "+room



    elif "연세대학교" in text or "yonsei" in text.lower():
        if "송도" in text:
            pattern = r'송도.*?호'
            matches = re.findall(pattern, text)
            try:
                text= "인천광역시 연수구 송도과학로 50 "+ matches[-1]
            except:
                text=""
        #gpt
        elif "Songdo" in text:
            order_text = """ocr 텍스트에서 거주지 서류 주인이 '송도0학사 O동 0000호'에 산다는 정보를 확인할 수 있어.
                            정보를 확인한 후, 해당되는 "숫자(0), 문자(O)"정보를 찾아 넣어 '송도0학사 O0000'과 같은 형식으로, 한글로 반환해줘."""
            info=ocr_to_gpt_subinfo(text,order_text).replace("'","")
            text= "인천광역시 연수구 송도과학로 50 " + info

        elif "SK Global House" in text:
            room = gemini_room(text)
            # room 값이 int로 변환되지 않는다면 한 번 더 호출
            try:
                int_room = int(room)
            except:
                room = gemini_room(text)

            if len(room)>5:
                text=""
            else:
                text = "서울특별시 서대문구 연세로 50 연세대학교 생활관 SK글로벌하우스 "+ room + "호"

        elif "법현학사" in text:
            room = gemini_room(text)
            # room 값이 int로 변환되지 않는다면 한 번 더 호출
            try:
                int_room = int(room)
            except:
                room = gemini_room(text)

            if len(room)>5:
                text=""
            else:
                text = "서울특별시 서대문구 연세로 50 연세대학교 법현학사 "+ room + "호"

        elif "국제학사" in text or "International House" in text:
            room = gemini_room(text)
            # room 값이 int로 변환되지 않는다면 한 번 더 호출
            try:
                int_room = int(room)
            except:
                room = gemini_room(text)

            if len(room)>5:
                text=""
            else:
                text = "서울특별시 서대문구 연세로 50 연세대학교 국제학사 "+ room + "호"

        elif "우정원" in text:
            room = gemini_room(text)
            # room 값이 int로 변환되지 않는다면 한 번 더 호출
            try:
                int_room = int(room)
            except:
                room = gemini_room(text)

            if len(room)>5:
                text=""
            else:
                text = "서울특별시 서대문구 연세로 50 연세대학교 우정원 "+ room + "호"

        elif "무악" in text:
            order_text = """ocr 텍스트에서 거주지 서류 주인이 '무악0학사 O동 0000호'에 산다는 정보를 확인할 수 있어.
                    정보를 확인한 후, 해당되는 "숫자(0), 문자(O)"정보를 찾아 넣어 '무악0학사 O동 0000호' 형식으로 반환해줘."""
            info=ocr_to_gpt_subinfo(text,order_text).replace("'","")
            text= "인천광역시 연수구 송도과학로 50 " + info

        else:
            text = ""
        



    #아직 코드에 미반영된 대학교 서류
    elif "대학교" in text or 'university' in text.lower():
        print("코드에 없는 대학교입니다")
        text2 = gpt_exception(find_by_pattern_threeline(text))

        #'대학교"가 쓰여있지만, 한글 주소 추출이 안되는 경우
        if text2 is None:
            print("영어로 된 기숙사 서류입니다.")
            try:
                pattern = r'(\d+[^,]+,[^,]+,[^\n]*(Seoul|-do|gyeonggido|Gyeonggido|Incheon|Gwangju|Busan|Daegu))'
                text = re.search(pattern, text).group(1)
                text=gpt_trans(text)
            except:
                text = text2
                text=gpt_trans(text)
        else:
            text = text2
        
    #기타 서류 or 영어로 된 서류
    else:
        print("영어로 된 기숙사 서류입니다.")
        try:
            pattern = r'(\d+[^,]+,[^,]+,[^\n]*(Seoul|-do|gyeonggido|Gyeonggido|Incheon|Gwangju|Busan|Daegu))'
            text = re.search(pattern, text).group(1)
            text=gpt_trans(text)
        except:
            text=gpt_trans(text)

    return text
    

