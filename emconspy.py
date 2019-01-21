#!/usr/bin/python3
# -*- coding: utf-8, vim: expandtab:ts=4 -*-

import os

import jnius_config


def import_pyjnius():
    """
    PyJNIus can only be imported once per Python interpreter and one must set the classpath before importing...
    """
    # Check if autoclass is already imported...
    if not jnius_config.vm_running:

        # Tested on Ubuntu 16.04 64bit with openjdk-8 JDK and JRE installed:
        # sudo apt install openjdk-8-jdk-headless openjdk-8-jre-headless

        # Set JAVA_HOME for this session
        try:
            os.environ['JAVA_HOME']
        except KeyError:
            os.environ['JAVA_HOME'] = '/usr/lib/jvm/java-8-openjdk-amd64/'

        # Set path and import jnius for this session
        from jnius import autoclass
    elif hasattr(jnius_config, 'classpath_show_warning') and not jnius_config.classpath_show_warning:
        from jnius import autoclass  # Warning already had shown. It is enough to show it only once!
    else:
        import sys
        from jnius import cast, autoclass
        class_loader = autoclass('java.lang.ClassLoader')
        cl = class_loader.getSystemClassLoader()
        ucl = cast('java.net.URLClassLoader', cl)
        urls = ucl.getURLs()
        cp = ':'.join(url.getFile() for url in urls)

        jnius_config.classpath_show_warning = False
        print('Warning: PyJNIus is already imported with the following classpath: {0} Please check if it is ok!'.
              format(cp), file=sys.stderr)

    # Return autoclass for later use...
    return autoclass


class EmConsPy:
    class_path = os.path.join(os.path.dirname(__file__), 'BerkeleyProdParser.jar') + ':' + os.path.dirname(__file__)
    vm_opts = '-Xmx4096m'

    def __init__(self, model_file=os.path.normpath(os.path.join(os.path.dirname(__file__), 'szk.const.model')),
                 source_fields=None, target_fields=None):
        if not jnius_config.vm_running:
            jnius_config.add_classpath(EmConsPy.class_path)
            jnius_config.add_options(EmConsPy.vm_opts)
        self._autoclass = import_pyjnius()
        self._jstr = self._autoclass('java.lang.String')
        self._jlist = self._autoclass('java.util.ArrayList')
        self._parser = self._autoclass('hu.u_szeged.cons.PPReplaceParser')
        self._parser.initReplaceParser(self._jstr(model_file.encode('UTF-8')), 4)
        # Field names for e-magyar TSV
        if source_fields is None:
            source_fields = {}

        if target_fields is None:
            target_fields = []

        self.source_fields = source_fields
        self.target_fields = target_fields

    def process_sentence(self, sen, field_names):
        parsed_sentence = self.parse_sentence((tok[field_names[0]], tok[field_names[1]], tok[field_names[2]])
                                              for tok in sen)
        for tok, out_label in zip(sen, parsed_sentence):
            tok.append(out_label)
        return sen

    @staticmethod
    def prepare_fields(field_names):
        return [field_names['form'], field_names['lemma'], field_names['xpostag']]

    def parse_sentence(self, lines):
        sent = self._jlist()

        # Read the text from TSV style input
        for curr_form, curr_lemma, curr_xpostag in lines:
            tok = self._jlist()
            tok.add(self._jstr(curr_form.encode('UTF-8')))
            tok.add(self._jstr(curr_lemma.encode('UTF-8')))
            tok.add(self._jstr(curr_xpostag.encode('UTF-8')))
            sent.add(tok)

        # Parse
        parsed_sentence = self._parser.parseSentenceEx(sent)

        # Return output as an iterator over tokens...
        return (tok[4] for tok in parsed_sentence)

    def parse_stream(self, stream):
        lines = []
        for line in stream:
            fields = line.strip().split('\t')
            if len(fields) == 0:
                for curr_line, label in zip(lines, self.parse_sentence(lines)):
                    yield '{0}\t{1}\n'.format(curr_line, label).encode('UTF-8')
                yield b'\n'
                lines = []
            else:
                lines.append(fields)
        if len(lines) > 0:
            for curr_line, label in zip(lines, self.parse_sentence(lines)):
                yield '{0}\t{1}\n'.format(curr_line, label).encode('UTF-8')


if __name__ == '__main__':
    dep_parser = EmConsPy()

    ex = 'A a [/Det|Art.Def]\n' \
         'kutya kutya [/N][Nom]\n' \
         'elment elmegy [/V][Prs.NDef.3Sg]\n' \
         'sétálni sétál [/V][Inf]\n' \
         '. . OTHER'

    for inp_line, output_label in zip(ex.split('\n'), dep_parser.parse_sentence(ex.split('\n'))):
        print(inp_line, output_label, sep='\t')
