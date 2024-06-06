import requests
from pdb import set_trace as st


def download_file_from_airtable(items:list,
                                           save_dir:str,
                                           save_name:str):
    '''
        item:       (list)  다운로드할 파일 (에어테이블 Attachment 양식)
                            형식 - users[idx]["fields"][필드명]
        save_dir:   (str) 다운로드 위치
        save_name:  (str) 파일명
    '''
    file_names:list = []
    for i, item in enumerate(items):
        # URL 가져오기
        url:str = item["url"].split("?")[0]
        
        # 파일명 설정
        file_type = item["type"].split("/")[-1]
        file_name = f"{save_dir}/{save_name}_{i:02d}.{file_type}"
        
        # 파일 다운로드
        with open(file_name, "wb") as file:
            res = requests.get(url)
            file.write(res.content)            
            file_names.append(file_name)
    
    return file_names