"""Translate subfolders and files of input folder path.
As a result next to supplied folder will be created a new one with translation.

TODO:
    Copy already renamed paths. Not like now: first copy, then rename.
    Add checking if text that was sent to translator
        is aligned with returned.
        Or no need? TBD
    Add checking if translated file name conflicts
        with existing but skipped for translation.
        So far no need, nothing is skipped.
"""

import os
import sys
import shutil
import requests
from halo import Halo
from pathlib import Path
from pprint import pprint
import pyinputplus as pyip
from pathvalidate import is_valid_filename, sanitize_filename
from translatepy.translators.google import GoogleTranslate


def print_path_tree(top: os.PathLike):
    """Print directory tree of input path."""
    top_count_sep = os.fspath(top).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(top):
        depth = dirpath.count(os.sep) - top_count_sep
        indent = ' ' * 2 * depth
        if os.path.samefile(top, dirpath):
            indent = ''
        print(f'{indent}📁 {os.path.basename(dirpath)}')
        sub_indent = ' ' * 2 * (depth + 1)
        for file in filenames:
            print(f'{sub_indent}🗋 {file}')


def list_tree(top: os.PathLike):
    """List the entire path tree walking top-down"""
    top_down_paths = []
    for dirpath, dirnames, filenames in os.walk(top):
        top_down_paths.append(dirpath)
        for filename in filenames:
            top_down_paths.append(os.path.join(dirpath, filename))
    return top_down_paths


def print_common_tree(paths: list):
    """Print common directory tree for supplied paths
    without accessing the filesystem.
    Works with both: os.PathLike and pathlib.PurePath.

    No icons as cannot properly define whether it is a file or directory
    without accessing the filesystem.
    Definition by suffix fails with folders having dots in name.
    """
    common_path = os.path.commonpath(paths)
    common_count_sep = common_path.count(os.sep)
    assert len(common_path) > 0, 'No common directory'
    print(f'🖴 {common_path}')
    for sub_path in paths:
        depth = str(sub_path).count(os.sep) - common_count_sep
        indent = ' ' * 2 * (depth)
        print(f'{indent} {os.path.basename(sub_path)}')


def pack_names_text(names_texts: dict):
    """Pack names text for translation.
    Prepare the list of unique texts and their keys
    from dict of enumerated names
    [['unique text one', 1, 3],
    ['unique text two', 2, 4],
    ['unique text three', 3, 5, 6]]
    """
    utexts_and_keys = []
    for u in set(names_texts.values()):
        utext = [u]  # first is unique text itself
        for i, sub_path in names_texts.items():
            # keys of values with this text
            if sub_path == u:
                utext.append(i)
        utexts_and_keys.append(utext)
    return utexts_and_keys


def assure_online(url: str):
    response = requests.get(url)
    response.raise_for_status()
    return response.status_code


def google_translator(texts: list, dest_lang: str):
    """Translate list of texts using Google Translate.
    Return TranslationResult Class"""
    SERVER_URL = 'translate.google.com'
    CLEAN_TRANSLATION_CACHE = False

    assure_online(f'http://{SERVER_URL}')

    g_translate = GoogleTranslate(service_url=SERVER_URL)
    translation_results = []

    for text in texts:
        translation = g_translate.translate(text, dest_lang)
        translation_results.append(translation)

    if CLEAN_TRANSLATION_CACHE is True:
        g_translate.clean_cache()
    return translation_results


def unpack_names_text(translated_list: list, utexts_and_keys: list):
    """Unpack translated text.
    Receive the list of translated texts and list of keys for these texts
    Convert them back to a dictionary of enumerated names.
    """
    translated_text_and_keys = []
    for trans_text, u_and_k in zip(translated_list, utexts_and_keys):
        new_text = [trans_text] + u_and_k[1:]
        translated_text_and_keys.append(new_text)

    translated_texts_dict = {}
    for text_and_keys in translated_text_and_keys:
        trans_text = text_and_keys[0]
        for i in text_and_keys[1:]:
            translated_texts_dict[i] = trans_text
    return translated_texts_dict


def show_translation_as(translated_texts: list, show_as: str = None):
    """Show text translated text as:
        show_as='rename': translation only
        show_as='prefix': translation [original text]
        show_as='suffix': original text [translation]
        """
    results = []
    for translation in translated_texts:
        if show_as == 'rename':
            result_text = translation.result
        elif show_as == 'prefix':
            result_text = f'{translation.result} [{translation.source}]'
        elif show_as == 'suffix':
            result_text = f'{translation.source} [{translation.result}]'
        else:
            result_text = translation.result
        results.append(result_text)
    return results


def validate_names(names: dict):
    """Validate folders and files names.
    Prompt for names auto-correction if they are not valid."""
    invalid_names_info = set()
    valid_names = {}
    for i, name_text in names.items():
        if not is_valid_filename(name_text):
            valid_name = sanitize_filename(name_text)
            valid_names[i] = valid_name
            invalid_names_info.add(f'{name_text} -> {valid_name}')

    if len(invalid_names_info) > 0:
        print('Following names are invalid for Windows OS'
              ' and have to be changed:')
        pprint(invalid_names_info)
        confirm_sanitized_names = pyip.inputYesNo('\nchange accordingly? Y/N')
        print(f'\n{confirm_sanitized_names}')
        if confirm_sanitized_names == 'yes':
            for i, name_text in valid_names.items():
                names[i] = name_text
        else:
            sys.exit('Canceled by user')


def new_folder_name(top: Path, extra_txt: str = ''):
    """New folder name to store translated files.\\
    Get new name for the name of given path with extra text (optional).\\
    If new name is busy, put incrementing number in the end."""
    new_name = f'{top.name}{extra_txt}'

    if Path.exists(top.parent / f'{new_name}'):
        i = 1
        while Path.exists(top.parent / f'{new_name} {i}'):
            i += 1
        return f'{new_name} {i}'
    else:
        return new_name


def get_copied_paths(subpaths: list, old_top_path: Path, new_top_path: Path):
    """Get paths of copied folders"""
    copied_subpaths = []
    for p in subpaths:
        rel_path = p.relative_to(old_top_path)
        new_path = Path(new_top_path, rel_path.parent, p.name)
        copied_subpaths.append(new_path)
    return copied_subpaths


def rename_paths(old_paths: list, new_paths: list):
    """Rename old paths to new paths in down-to-top order"""
    for old_path, new_path in zip(reversed(new_paths),
                                  reversed(old_paths)):
        old_path.rename(new_path)


top_path = Path(pyip.inputFilepath('\n Input folder path\n', mustExist=True))

# have to assert, as mustExist in inputFilepath didn't work
assert top_path.exists(), 'Input path does not exist'
assert top_path.is_dir(), 'Input path is not a folder'

print('\n Folder structure of selected path:')

print_path_tree(top_path)
print('\n')

tree = list_tree(top_path)
subpaths = [Path(p) for p in tree[1:]]  # ignore the top path
subpaths_dict = {k: v for k, v in enumerate(subpaths)}

# collect names texts and files extensions
names_texts = {}
names_suffixes = {}
for i, sub_path in subpaths_dict.items():
    if sub_path.is_dir():
        names_texts[i] = sub_path.name
    elif sub_path.is_file():
        names_texts[i] = sub_path.stem
        names_suffixes[i] = sub_path.suffix

# prepare unique texts
utexts_and_keys = pack_names_text(names_texts)
unique_texts = [ut[0] for ut in utexts_and_keys]

# destination language
dest_lang = pyip.inputStr('Input destination language abbreviation'
                          ' (e.g., ru, en, zh-cn ).\n')
print(f'\n{dest_lang}\n')

# waiting spinner for terminal
spin_dots = {'interval': 300, 'frames': [' ∙●', ' ●∙']}
spinner = Halo(text='translating', spinner=spin_dots)
spinner.start()

# translating
translation_results = google_translator(unique_texts, dest_lang)

spinner.stop()
print('\n')

# show translation as
translation_as = pyip.inputChoice(['rename', 'prefix', 'suffix'],
                                  'Translation complete. '
                                  'Show translation as:\n'
                                  '    rename: translation only\n'
                                  '    prefix: translation [original text]\n'
                                  '    suffix: original text [translation]\n')
print(f'\n{translation_as}\n')
translated_texts = show_translation_as(translation_results, translation_as)
unpacked_translation = unpack_names_text(translated_texts, utexts_and_keys)

# add file extension to name if it had any
translated_names = {}
for i, sub_path in unpacked_translation.items():
    translated_names[i] = sub_path + names_suffixes.get(i, '')

validate_names(translated_names)

new_dir = new_folder_name(top_path, ' - Translated')
new_dir_path = Path(top_path.parent, new_dir)

# translated paths dict
translated_paths_dict = {}
for i, old_path in subpaths_dict.items():
    rel_path = old_path.relative_to(top_path)
    new_path = Path(new_dir_path, rel_path.parent, translated_names[i])
    translated_paths_dict[i] = new_path

# list of translated paths sorted by keys of dict
# sorting is to avoid 'unordered dict' issue
translated_paths = [v for k, v in sorted(translated_paths_dict.items())]

print('\nPreview translated:')
print_common_tree(translated_paths)

confirm_copy = pyip.inputYesNo(
    '\n Confirm creating new folder with translation? Y/N \n')
print(f'\n{confirm_copy}')

# copy to new folder and rename all the subpaths
if confirm_copy == 'yes':
    shutil.copytree(top_path, new_dir_path)
    copied_subpaths = get_copied_paths(subpaths, top_path, new_dir_path)
    rename_paths(translated_paths, copied_subpaths)
    print('\n New folder creation succeed. Results:')
    print_path_tree(new_dir_path)
