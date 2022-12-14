from __future__ import print_function
# Python version of oref0-autotune.sh
# Original bash code: scottleibrand, pietergit, beached, danamlewis

# This script sets up an easy test environment for autotune, allowing the user to vary parameters
# like start/end date and number of runs.
#
# Required Inputs:
#   DIR, (--dir=<OpenAPS Directory>)
#   NIGHTSCOUT_HOST, (--ns-host=<NIGHTSCOUT SITE URL)
#   START_DATE, (--start-date=<YYYY-MM-DD>)
# Optional Inputs:
#   END_DATE, (--end-date=<YYYY-MM-DD>)
#     if no end date supplied, assume we want a months worth or until day before current day
#   NUMBER_OF_RUNS (--runs=<integer, number of runs desired>)
#     if no number of runs designated, then default to 5
#   EXPORT_EXCEL (--xlsx=<filenameofexcel>)
#     export to excel. Disabled by default
#   TERMINAL_LOGGING (--log <true/false(true)>
#     logs terminal output to autotune.<date stamp>.log in the autotune directory, default to true


import argparse
import requests
import datetime
import os, errno
import logging
import pytz
from subprocess import call
import shutil
import six


def get_input_arguments():
    parser = argparse.ArgumentParser(description='Autotune')

    # Required
    # NOTE: As the code runs right now, this directory needs to exist and as well as the subfolders: autotune, settings
    parser.add_argument('--dir',
                        '-d',
                        type=str,
                        required=True,
                        help='(--dir=<OpenAPS Directory>)')
    parser.add_argument('--ns-host',
                        '-n',
                        type=str,
                        required=True,
                        metavar='NIGHTSCOUT_HOST',
                        help='(--ns-host=<NIGHTSCOUT SITE URL)')
    parser.add_argument('--start-date',
                        '-s',
                        type=lambda d: datetime.datetime.strptime(d, '%Y-%m-%d'),
                        required=True,
                        help='(--start-date=<YYYY-MM-DD>)')
    # Optional
    parser.add_argument('--end-date',
                        '-e',
                        type=lambda d: datetime.datetime.strptime(d, '%Y-%m-%d'),
                        help='(--end-date=<YYYY-MM-DD>) ')
    parser.add_argument('--runs',
                        '-r',
                        type=int,
                        metavar='NUMBER_OF_RUNS',
                        help='(--runs=<integer, number of runs desired>)')
    parser.add_argument('--xlsx',
                        '-x',
                        type=str,
                        metavar='EXPORT_EXCEL',
                        help='(--xlsx=<filenameofexcel>)')
    parser.add_argument('--log',
                        '-l',
                        type=bool,
                        default=True,
                        metavar='TERMINAL_LOGGING',
                        help='(--log <true/false(true)>)')

    return parser.parse_args()

def assign_args_to_variables(args):
    # TODO: Input checking.

    # On Unix and Windows, return the argument with an initial component of
    # ~ or ~user replaced by that user's home directory.
    directory = os.path.expanduser(args.dir)
    nightscout_host = args.ns_host
    start_date = args.start_date
    end_date = args.end_date or datetime.datetime.today()
    number_of_runs = args.runs or 1
    export_excel = args.xlsx
    recommends_report = args.log

    return directory, nightscout_host, start_date, end_date, number_of_runs, export_excel, recommends_report

def get_nightscout_profile(nightscout_host, directory):
    #TODO: Add ability to use API secret for Nightscout.
    res = requests.get(nightscout_host + '/api/v1/profile.json')
    with open(os.path.join(directory, 'autotune', 'nightscout.profile.json'), 'w') as f:  # noqa: F821
        f.write(six.ensure_str(res.text, encoding='utf-8'))

def get_openaps_profile(directory):
    shutil.copy(os.path.join(directory, 'settings', 'pumpprofile.json'), os.path.join(directory, 'autotune', 'profile.pump.json'))

    # If a previous valid settings/autotune.json exists, use that; otherwise start from settings/profile.json

    # This allows manual users to be able to run autotune by simply creating a settings/pumpprofile.json file.
    # cp -up settings/pumpprofile.json settings/profile.json
    shutil.copy(os.path.join(directory, 'settings', 'pumpprofile.json'), os.path.join(directory, 'settings', 'profile.json'))

    # TODO: Get this to work. For now, just copy from settings/profile.json each time.
    # If a previous valid settings/autotune.json exists, use that; otherwise start from settings/profile.json
    # cp settings/autotune.json autotune/profile.json && cat autotune/profile.json | json | grep -q start || cp autotune/profile.pump.json autotune/profile.json
    # create_autotune_json = "cp {0}settings/autotune.json {0}autotune/profile.json && cat {0}autotune/profile.json | json | grep -q start || cp {0}autotune/profile.pump.json {0}autotune/profile.json".format(directory)
    # print create_autotune_json
    # call(create_autotune_json, shell=True)

    # cp settings/profile.json settings/autotune.json
    shutil.copy(os.path.join(directory, 'settings', 'profile.json'), os.path.join(directory, 'settings', 'autotune.json'))

    # cp settings/autotune.json autotune/profile.json
    shutil.copy(os.path.join(directory, 'settings', 'autotune.json'), os.path.join(directory, 'autotune', 'profile.json'))

    # cp settings/autotune.json autotune/pumpprofile.json
    shutil.copy(os.path.join(directory, 'settings', 'autotune.json'), os.path.join(directory, 'autotune', 'pumpprofile.json'))

    #TODO: Do the correct copying here.
    # cat autotune/profile.json | json | grep -q start || cp autotune/profile.pump.json autotune/profile.json'])

def get_nightscout_carb_and_insulin_treatments(nightscout_host, start_date, end_date, directory):
    logging.info('Grabbing NIGHTSCOUT treatments.json for date range: {0} to {1}'.format(start_date, end_date))
    output_file_name = os.path.join(directory, 'autotune', 'ns-treatments.json')

    def _normalize_datetime(dt):
        dt = dt.replace(hour=20, minute=0, second=0, microsecond=0, tzinfo=None)
        dt = pytz.timezone('US/Eastern').localize(dt)
        return dt

    start_date = _normalize_datetime(start_date)
    end_date = _normalize_datetime(end_date)
    url='{0}/api/v1/treatments.json?find\[created_at\]\[\$gte\]=`date --date="{1} -4 hours" -Iminutes`&find\[created_at\]\[\$lte\]=`date --date="{2} +1 days" -Iminutes`'.format(nightscout_host, start_date, end_date)
    #TODO: Add ability to use API secret for Nightscout.
    res = requests.get(url)
    with open(output_file_name, 'w') as f:
        f.write(six.ensure_str(res.text, 'utf-8'))

def get_nightscout_bg_entries(nightscout_host, start_date, end_date, directory):
    logging.info('Grabbing NIGHTSCOUT enries/sgv.json for date range: {0} to {1}'.format(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
    date_list = [start_date + datetime.timedelta(days=x) for x in range(0, (end_date - start_date).days)]

    for date in date_list:
        url="{0}/api/v1/entries/sgv.json?find\[date\]\[\$gte\]={1}&find\[date\]\[\$lte\]={1}`&count=1500"
        url = url.format(nightscout_host, date)
        #TODO: Add ability to use API secret for Nightscout.
        res = requests.get(url)
        with open(os.path.join(directory, 'autotune', 'ns-entries.{date}.json'.format(date=date.strftime("%Y-%m-%d"))), 'w') as f:
            f.write(six.ensure_str(res.text, 'utf-8'))

def run_autotune(start_date, end_date, number_of_runs, directory):
    date_list = [start_date + datetime.timedelta(days=x) for x in range(0, (end_date - start_date).days)]
    autotune_directory = os.path.join(directory, 'autotune')
    FNULL = open(os.devnull, 'w')
    for run_number in range(1, number_of_runs + 1):
        for date in date_list:
            # cp profile.json profile.$run_number.$i.json
            shutil.copy(os.path.join(autotune_directory, 'profile.json'),
                        os.path.join(autotune_directory, 'profile.{run_number}.{date}.json'
                        .format(run_number=run_number, date=date.strftime("%Y-%m-%d"))))

            # Autotune Prep (required args, <pumphistory.json> <profile.json> <glucose.json>), output prepped glucose
            # data or <autotune/glucose.json> below
            # oref0-autotune-prep ns-treatments.json profile.json ns-entries.$DATE.json > autotune.$RUN_NUMBER.$DATE.json
            ns_treatments = os.path.join(autotune_directory, 'ns-treatments.json')
            profile = os.path.join(autotune_directory, 'profile.json')
            pump_profile = os.path.join(autotune_directory, "pumpprofile.json")
            ns_entries = os.path.join(autotune_directory, 'ns-entries.{date}.json'.format(date=date.strftime("%Y-%m-%d")))

            # autotune.$RUN_NUMBER.$DATE.json
            autotune_run_filename = os.path.join(autotune_directory, 'autotune.{run_number}.{date}.json'
                                                 .format(run_number=run_number, date=date.strftime("%Y-%m-%d")))
            autotune_prep = 'oref0-autotune-prep {ns_treatments} {profile} {ns_entries} {pump_profile} --output-file {autotune_run_filename}'.format(ns_treatments=ns_treatments, profile=profile, ns_entries=ns_entries, pump_profile=pump_profile, autotune_run_filename=autotune_run_filename)
            logging.info('Running {script}'.format(script=autotune_prep))
            call(autotune_prep, stdout=FNULL, shell=True)
            logging.info('Writing output to {filename}'.format(filename=autotune_run_filename))

            # Autotune  (required args, <autotune/glucose.json> <autotune/autotune.json> <settings/profile.json>),
            # output autotuned profile or what will be used as <autotune/autotune.json> in the next iteration
            # oref0-autotune-core autotune.$RUN_NUMBER.$DATE.json profile.json profile.pump.json > newprofile.$RUN_NUMBER.$DATE.json

            # oref0-autotune-core autotune.$run_number.$i.json profile.json profile.pump.json > newprofile.$RUN_NUMBER.$DATE.json
            profile_pump = os.path.join(autotune_directory, 'profile.pump.json')

            # newprofile.$RUN_NUMBER.$DATE.json
            newprofile_run_filename = os.path.join(autotune_directory, 'newprofile.{run_number}.{date}.json'
                                                   .format(run_number=run_number, date=date.strftime("%Y-%m-%d")))
            autotune_core = 'oref0-autotune-core {autotune_run} {profile} {profile_pump} --output-file {newprofile_run_filename}'.format(profile=profile, profile_pump = profile_pump, autotune_run=autotune_run_filename, newprofile_run_filename=newprofile_run_filename)
            logging.info('Running {script}'.format(script=autotune_core))
            call(autotune_core, stdout=FNULL, shell=True)
            logging.info('Writing output to {filename}'.format(filename=newprofile_run_filename))

            # Copy tuned profile produced by autotune to profile.json for use with next day of data
            # cp newprofile.$RUN_NUMBER.$DATE.json profile.json
            shutil.copy(os.path.join(autotune_directory, 'newprofile.{run_number}.{date}.json'.format(run_number=run_number, date=date.strftime("%Y-%m-%d"))),
                        os.path.join(autotune_directory, 'profile.json'))

def export_to_excel(output_directory, output_excel_filename):
    autotune_export_to_xlsx = 'oref0-autotune-export-to-xlsx --dir {0} --output {1}'.format(output_directory, output_excel_filename)
    call(autotune_export_to_xlsx, shell=True)

def create_summary_report_and_display_results(output_directory):
    print()
    print("Autotune pump profile recommendations:")
    print("---------------------------------------------------------")

    report_file = os.path.join(output_directory, 'autotune', 'autotune_recommendations.log')
    autotune_recommends_report = 'oref0-autotune-recommends-report {0}'.format(output_directory)

    call(autotune_recommends_report, shell=True)
    print("Recommendations Log File: {0}".format(report_file))

    # Go ahead and echo autotune_recommendations.log to the terminal, minus blank lines
    # cat $report_file | egrep -v "\| *\| *$"
    call(['cat {0} | egrep -v "\| *\| *$"'.format(report_file)], shell=True)

if __name__ == "__main__":
    # Set log level for this app to DEBUG.
    logging.basicConfig(level=logging.DEBUG)
    # Supress non-essential logs (below WARNING) from requests module.
    logging.getLogger("requests").setLevel(logging.WARNING)

    args = get_input_arguments()
    directory, nightscout_host, start_date, end_date, number_of_runs, export_excel, recommends_report = assign_args_to_variables(args)

    # TODO: Convert Nightscout profile to OpenAPS profile format.
    #get_nightscout_profile(NIGHTSCOUT_HOST, DIR)

    get_openaps_profile(directory)
    get_nightscout_carb_and_insulin_treatments(nightscout_host, start_date, end_date, directory)
    get_nightscout_bg_entries(nightscout_host, start_date, end_date, directory)
    run_autotune(start_date, end_date, number_of_runs, directory)

    if export_excel:
        export_to_excel(directory, export_excel)

    if recommends_report:
        create_summary_report_and_display_results(directory)
