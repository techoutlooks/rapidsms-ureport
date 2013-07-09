from rapidsms_ureport.ureport.utils import configure_messages_for_script

__author__ = 'argha'

from django.core.management.base import BaseCommand


def parse_line(line,separator='='):
    tokens_list = line.split(separator)
    return  int(tokens_list[0]), tokens_list[1].strip('\n')


class Command(BaseCommand):
    def handle(self, *args, **options):
        if len(args) < 1:
            print("You must pass the file with custom messages as an argument.")
            exit(-1)
        else:
            file_as_list = list(open(args[0]))
            messages_dict = {}
            for line in file_as_list:
                key,value = parse_line(line)
                messages_dict[key] = value
            configure_messages_for_script('ureport_autoreg2', messages_dict)