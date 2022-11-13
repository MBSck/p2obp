#!/usr/bin/env python3

""" Parse OB Plan

This script parses the night plans made with Roy van Boekel's "calibrator_find"
IDL script into a (.yaml)-file that contains the CALs sorted to their
corresponding SCI-targets in a dictionary that first specifies the run, then
the night and then the SCIs, CALs and TAGs (If calibrator is LN/N or L-band).

This tool accepts (.txt)-files.

The script requires that `yaml` be installed within the Python environment this
script is run in.

This file can also be imported as a module and contains the following functions:
    * readout_txt - reads a (.txt)-file into its individual lines returning them
    * save_dictionary - Saves a dictionary as a (.yaml)-file
    * check_lst4elem - Checks a list for an element and returns a bool
    * get_file_section - Gets a section of the (.txt)/lines
    * get_sci_cal_tag_lst - Gets the individual lists of the SCI, CAL and TAG
    * parse_night_plan - The main function of the script. Parses the night plan

Example of usage:
    >>> from parseOBplan import parse_night_plan
    >>> path = "/Users/scheuck/Documents/PhD/matisse_stuff/observation/P109/"\
    >>>         "april2022/p109_MATISSE_YSO_runs_observing_plan_v0.1.txt"
    >>> run_dict = parse_night_plan(path, save2file=True)
    >>> print(run_dict)
    ... {'run 5, 109.2313.005 = 0109.C-0413(E)': {'nights 2-4: {'SCI': ['MY Lup', ...], 'CAL': [['HD142198'], ...], 'TAG': [['LN'], ...]}}}
"""

# TODO: Make parser accept more than one calibrator block for one night, by
# checking if there are integers for numbers higher than last calibrator and
# then adding these

# TODO: Think about making the parsing work differently, check what readlines
# accept -> Make similar to loadbobx, readblock and so...
import os
import yaml
import warnings

from pathlib import Path
from typing import Dict, List, Optional


def contains_element(list_to_search: List, element_to_search: str) -> bool:
    """Checks if an element is in the list searched and returns 'True' or 'False'

    Parameters
    ----------
    list_to_search: List
        The list to be searched in
    element_to_search: str
        The element being searched for

    Returns
    -------
    element_in_list: bool
        'True' if element is found, 'False' otherwise
    """
    return any([element_to_search == element for element in list_to_search])


def get_file_section(lines: List, identifier: str) -> List:
    """Gets the section of a file corresponding to the given identifier and
    returns a dict with the keys being the match to the identifier and the
    values being a subset of the lines list

    Parameters
    ----------
    lines: List
        The lines read from a file
    identifier: str
        The identifier by which they should be split into subsets

    Returns
    --------
    subset: dict
        A dict that contains a subsets of the original lines
    """
    indices, labels = [], []
    for index, line in enumerate(lines):
        if (identifier in line.lower()) and (line.split()[0].lower() == identifier):
            indices.append(index)
            labels.append(line.replace('\n', ''))

    if not indices:
        indices, labels = [0], ["full_" + identifier]

    sections = [lines[index:] if len(indices) == 1 else \
                  lines[index:indices[i+1]] for i, index in enumerate(indices)]

    return {labels: sections for (labels, sections) in zip(labels, sections)}


def get_targets_calibrators_tags(lines: List):
    """Gets the info for the SCI, CAL and TAGs from the individual lines

    Parameters
    -----------
    lines: List
        The lines to be parsed

    Returns
    -------
    Dict:
        A dictionary that contains the SCI, CAL and TAG lists
    """
    line_start = [index for index, line in enumerate(lines) if line[0].isdigit()][0]
    line_end = [index for index, line in enumerate(lines) if "calibrator_find" in line][0]
    lines = ['' if line == '\n' else line for line in lines[line_start:line_end]]

    sci_lst, cal_lst, tag_lst  = [], [[]], [[]]
    double_sci, counter = False, 0

    for index, line in enumerate(lines):
        try:
            if ((line == '') or (not line.split()[0][0].isdigit()))\
               and (lines[index+1].split()[0][0].isdigit()):
                counter += 1
                cal_lst.append([])
                tag_lst.append([])

            else:
                line = line.split(' ')
                if (line[0][0].isdigit()) and (len(line) > 2)\
                   and (len(line[0].split(":")) == 2):
                    # NOTE: Gets the CAL
                    if "cal_" in line[1]:
                        temp_cal = line[1].split("_")
                        cal_lst[counter].append(temp_cal[2])
                        tag_lst[counter].append(temp_cal[1])

                        if double_sci:
                            cal_lst.append([])
                            tag_lst.append([])
                            cal_lst[counter+1].append(temp_cal[2])
                            tag_lst[counter+1].append(temp_cal[1])
                            double_sci = False
                    else:
                        # NOTE: Fixes the case where one CAL is for two SCI
                        if (index != len(lines)-3):
                            try:
                                if lines[index+1][0][0].isdigit() and\
                                   not ("cal_" in lines[index+1].split(' ')[1]) and\
                                   lines[index+2][0][0].isdigit():
                                    double_sci = True
                            except:
                                pass

                        # NOTE: Gets the SCI
                        if line[3] != '':
                            sci_lst.append((line[1]+' '+line[2]+' '+line[3]).strip())
                        else:
                            sci_lst.append((line[1]+' '+line[2]).strip())
        except:
            pass

    return {"SCI": sci_lst, "CAL": cal_lst, "TAG": tag_lst}


def parse_night_plan(night_plan_path: Path,
                     run_identifier: Optional[str] = "run",
                     sub_identifier: Optional[str] = "night",
                     save_to_file: bool = False) -> Dict[str, List]:
    """Parses the night plan created with 'calibrator_find.pro' into the
    individual runs as key of a dictionary, specified by the 'run_identifier'.
    If no match is found then it parses the whole night to 'run_identifier's
    or the 'default_key', respectively.

    Parameters
    ----------
    night_plan_path: Path
        The night plan of the '.txt'-file format to be read and parsed
    run_identifier: str, optional
        Set to default identifier that splits the individual runs into keys of
        the return dict as 'run'
    sub_identifier: str, optional
        Set to default sub identifier that splits the individual runs into the
        individual nights. That is, in keys of the return dict as 'night'
    save_to_file: bool, optional
        If this is set to true then it saves the dictionary as
        'night_plan.yaml', Default is 'False'

    Returns
    -------
    night_dict: Dict
        A dict that contains the <default_search_param> as key and a list
        containing the sub lists 'sci_lst', 'cal_lst' and 'tag_lst'
    """
    night_plan_dict = {}
    try:
        with open(night_plan_path, "r+") as f:
            lines = f.readlines()
    except FileNotFoundError:
        warning.warn(f"File {night_plan_path} was not found/does not exist!")
        return night_plan_dict

    runs = get_file_section(lines, run_identifier)

    for label, section in runs.items():
        temp_subsection_dict = get_file_section(section, sub_identifier)

        nights = {}
        for sub_label, sub_section in temp_subsection_dict.items():
            if contains_element(sub_section, "cal_"):
                nights[sub_label] = get_targets_calibrators_tags(sub_section)

        night_plan_dict[label] = nights

    if save_to_file:
        with open(output_path, "w+") as yaml_file:
            yaml.safe_dump(night_plan_dict, yaml_file)

    return night_plan_dict


if __name__ == "__main__":
    data_path = "/Users/scheuck/Data/observations/P109/"
    specific_path = "september2022/p109_observing_plan_v0.1.txt"
    path = os.path.join(data_path, specific_path)
    run_dict = parse_night_plan(path, save_to_file=True)

    # NOTE: Check to verify
    for label, section in run_dict.items():
        if "run 6" in label:
            print(label, section)
