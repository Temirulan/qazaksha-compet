from __future__ import print_function

from googleapiclient import discovery
from httplib2 import Http
from oauth2client import file, client, tools

def press_f(message):
  print('Task successfully processed: {}'.format(message))
  x = input('Press f to continue:')
  if x != 'f': exit(0)

def parse_bracket(s):
  return s[s.find('{')+1:s.find('}')]




'''
Parsing book_structure. Parsed structure:
[
  {
    'name': 'I  Basic techniques',
    'chapters': [
      {
        'name': '1  Introduction',
        'sections': ['name': '1.1  Programming Languages', 'text': 'asdasd']
      }
    ]
  }
]
'''
temp_data = []
with open('cphb/book.tex', 'r') as f:
  rows = f.read().split('\n')
  open_part = False
  for row in rows:
    if 'part' in row:
      temp_data.append({'name': parse_bracket(row), 'chapters': []})
      open_part = True
    elif 'include' in row and open_part:
      temp_data[-1]['chapters'].append({'name': parse_bracket(row), 'sections': []})
    else:
      open_part = False

def parse_chapter(chapter_name):
  with open("cphb/{}.tex".format(chapter_name), 'r') as f:
    rows = f.read().split('\n')
    name = None
    sections = []
    for row in rows:
      if '\chapter' in row or '\section' in row:
        sections.append({'name': parse_bracket(row), 'text': ''})
      else:
        sections[-1]['text'] = sections[-1]['text'] + '\n' + row
    return {'name': sections[0]['name'], 'sections': sections}

part_index, chapter_index = 0, 0
book_structure = []
for part in temp_data:
  part_index += 1
  res = {}
  res['name'] = "{}  {}".format("I" * part_index, part['name'])
  res['chapters'] = []
  for chapter in part['chapters']:
    chapter_index += 1
    new_chapter = parse_chapter(chapter['name'])
    new_chapter['name'] = "{}  {}".format(str(chapter_index), new_chapter['name'])
    section_index = -1
    for i, sec in enumerate(new_chapter['sections']):
      section_index += 1
      new_chapter['sections'][i]['name'] = "{}.{}  {}".format(str(chapter_index), str(section_index), sec['name'])
    res['chapters'].append(new_chapter)
  book_structure.append(res)

press_f('Book structure parsed')




'''
Prepare tree-format for whole book. Format:
[
  {
    'name': 'folder name',
    'type': 'folder',
    'mimeType': 'application/vnd.google-apps.folder',
    'contents': [
      {
        'name': 'fname',
        'type': 'file',
        'mimeType': 'application/vnd.google-apps.document',
        'text': 'asd'
      }
    ]
  }
]
'''
directory_structure = {
  'name': 'Qazaqsha compet',
  'type': 'folder',
  'mimeType': 'application/vnd.google-apps.folder',
  'content': []
}
for part in book_structure:
  part_folder = {
    'name': part['name'],
    'type': 'folder',
    'mimeType': 'application/vnd.google-apps.folder',
    'content': []
  }
  for chapter in part['chapters']:
    chapter_folder = {
      'name': chapter['name'],
      'type': 'folder',
      'mimeType': 'application/vnd.google-apps.folder',
      'content': []
    }
    for section in chapter['sections']:
      doc = {
        'name': section['name'],
        'type': 'file',
        'mimeType': 'application/vnd.google-apps.document',
        'text': section['text']
      }
      chapter_folder['content'].append(doc)
    part_folder['content'].append(chapter_folder)
  directory_structure['content'].append(part_folder)

press_f('directory structure')


"""
Working with google api to create folders, files a.k.a docs
with prefilled message
"""
SCOPES = 'https://www.googleapis.com/auth/drive  https://www.googleapis.com/auth/documents'
store = file.Storage('storage.json')
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('client_id.json', SCOPES)
    creds = tools.run_flow(flow, store)
DRIVE = discovery.build('drive', 'v3', http=creds.authorize(Http()))
DOCS = discovery.build('docs', 'v1', http=creds.authorize(Http()))

files = []

DISCLAIMER = "Ниже приведена примерная копия текста главы которую надо перевести. Для удобства советуем смотреть в сам учебник, данный текст оставлен чтобы вы не запутались в количестве текста в данной главе."

def InsertText(text):
  return {'insertText': {'location': {'index': 1}, 'text': text}}

def TextStyle(length, font, style = None, b = True):
  result = []
  if style:
    result.append({
      'updateTextStyle': {
        'textStyle': {style: b},
        'fields': style,
        'range': {'startIndex': 1, 'endIndex': 1+length}
      }})
  result.append({
    'updateTextStyle': {
      'textStyle': {'fontSize': {'magnitude': font, 'unit': 'PT'}},
      'fields': 'fontSize',
      'range': {'startIndex': 1, 'endIndex': 1+length}
    }})
  return result
  

def write_disclaimer(file_id, name, text):
  requests = [InsertText(text)]
  requests.extend(TextStyle(len(text), 12))
  requests.append(InsertText('\n'))
  requests.append(InsertText(name))
  requests.extend(TextStyle(len(name), 16, 'bold'))
  requests.append(InsertText('\n\n'))
  requests.append(InsertText(DISCLAIMER))
  requests.extend(TextStyle(len(DISCLAIMER), 12, 'italic'))
  requests.append(InsertText('\n\n'))
  requests.append(InsertText('~' * 120))
  requests.extend(TextStyle(120, 12, 'bold', False))
  requests.append(InsertText('\n\n'))
  requests.append(InsertText('(write your translation here)'))
  DOCS.documents().batchUpdate(documentId=file_id, body={'requests': requests}).execute()

def dfs(data, par_id = None):
  print('Processing {}...'.format(data['name']))
  if data is None: return
  file_metadata = {
    'name': data['name'],
    'mimeType': data['mimeType']
  }
  if par_id:
    file_metadata['parents'] = [par_id]
  file = DRIVE.files().create(body=file_metadata, fields='id').execute()
  if data['type'] == 'file':
    permission = {'type': 'anyone', 'role': 'writer'}
    DRIVE.permissions().create(fileId=file.get('id'), body=permission).execute()
    files.append(file)
    write_disclaimer(file.get('id'), data.get('name', ''), data.get('text', ''))
    return
  for content in data['content']: dfs(content, file.get('id'))

dfs(directory_structure)

for x in files:
  print(DOCS.documents().get(documentId=x.get('id')).execute().get('title'))

for x in files:
  print(f"https://docs.google.com/document/d/{x.get('id')}")

