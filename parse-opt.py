import sys

fh = open(sys.argv[1],'r')
text = fh.read()
lines = text.split('\r\n')
if 1 == len(lines) :
    lines = text.split('\n')

options = {}
for line in lines :
    print(line)
    if 0 == len(line) : break;
    tokens = line.split()
    lrel = None
    rrel = None
    if 6 == len(tokens) :
        name = tokens[3]
        lrel = tokens[1:3]
        rrel = tokens[4:6]
    elif 4 == len(tokens) :
        if tokens[1][1].isdigit() :
            name = tokens[3]
            lrel = tokens[1:3]
        else :
            name = tokens[1]
            rrel = tokens[2:4]
    elif 2 == len(tokens) :
        name = tokens[1]
    else :
        raise RuntimeError('Invalid line: "%s"'%(line))
    t = options.get(name)
    if t :
        raise RuntimeError('option "%s" already exists: %s'%(name,t.string()))
    options[name] = { 'name':name, 'type':tokens[0], 'lrel':lrel, 'rrel':rrel }

def as_ctype(t) :
    if 'string' == t :
        return 'char *'
    if 'uint8' == t :
        return 'uint8_t'
    if 'uint16' == t :
        return 'uint16_t'
    if 'uint32' == t :
        return 'uint32_t'
    if 'double' == t :
        return t
    if 'bool' == t :
        return t
    if 'switch' == t :
        return None

struct_option = """struct option options[%d] = {
"""
format_struct_option = """  { .name = "%s", .has_arg = %d, .flag = NULL, .val = %s },
"""

support_code = """
int parse_double(const char *arg, double *value) {
  if(1 != sscanf(arg,"%lg",value)) return -1;
  return 0;
}

void dump_switch(const char *name) {
  printf("  switch %s: set\\n",name);
}

void dump_string(const char *name, const char *value) {
  printf("  string %s: '%s'\\n",name,value);
}

void dump_double(const char *name, double value) {
  printf("  double %s: '%lg'\\n",name,value);
}

void dump_uint8(const char *name, uint8_t value) {
  printf("  uint16 %s: '%u / 0x%02x'\\n",name,value,value);
}

void dump_uint16(const char *name, uint16_t value) {
  printf("  uint16 %s: '%u / 0x%04x'\\n",name,value,value);
}

void dump_uint32(const char *name, uint32_t value) {
  printf("  uint32 %s: '%u / 0x%08x'\\n",name,value,value);
}

void dump_flag(const char *name) {
  printf("  option %s: is set\\n",name);
}
"""
uint_template = """
int parse_uint%s(const char *arg, uint%s_t *value) {
  unsigned long long iv;
  if(1 != sscanf(arg,"%%llu",&iv)) return -1;
  *value = iv;
  if('-' == arg[0]) {
    iv = ~iv;
    iv -= (uint%s_t)(~*value);
  } else {
    iv ^= *value;
  }
  if(iv) return -2;
  return 0;
}
"""

for bit in [ '8','16','32' ] :
    support_code += uint_template % (bit,bit,bit)

enums = 'enum { LONG_START = 1023'

def gen_get_value(ptype,cname,name) :
    if None == ctype : return ''
    if 'string' == ptype :
        return """
      cmdline_options.%s.value = optarg;""" % (cname)
    if 'bool' == ptype :
        return """
      cmdline_options.%s.value = 1;""" % (cname)
    text = """
      switch(parse_%s(optarg,&cmdline_options.%s.value)) {
        case 0:
          break;"""%(ptype,cname)
    text += """
        case -1:
          fprintf(stderr,"Error: parsing %s from --%s=%%s\\n",optarg);
          exit(1);
          break;"""%(ptype,name)
    text += """
        case -2:
          fprintf(stderr,"Error: value --%s=%%s can not fit in %s\\n",optarg);
          exit(1);
          break;
      }"""%(name,ptype)
    return text

def gen_check_value(lrel,cname,rrel,name) :
    text = ''
    value = 'cmdline_options.%s.value' % (cname)
    if lrel :
        text += """
      if(!(%s %s %s)) {
        fprintf(stderr,"Error: --%s=%%s fails test %s %s %%s\\n",optarg,optarg);
        exit(1);
      }""" % (lrel[0],lrel[1],value,name,lrel[0],lrel[1])
    if rrel :
        text += """
      if(!(%s %s %s)) {
        fprintf(stderr,"Error: --%s=%%s fails test %%s %s %s\\n",optarg,optarg);
        exit(1);
      }""" % (value,rrel[0],rrel[1],name,rrel[0],rrel[1])
    return text

class Function_Code :
    def __init__(self) :
        self.body = []
    def add(self,option) :
        text = """
    case %s:
      cmdline_options.%s.set = 1;""" % (option['enum'],option['cname'])
        text += gen_get_value(option['type'],option['cname'],option['name'])
        text += gen_check_value(option['lrel'],option['cname'],option['rrel'],name)
        text += """
      break;
"""
        self.body.append(text)
    def render(self) :
        text = """
void cmdline_parse(int argc, char *argv[]) {
  int done = 0;
  do {
    int indexptr, ch;
    switch(ch = getopt_long(argc,argv,"h",options,&indexptr)) {"""
        text += "".join(self.body)
        text += """
    case 'h':
      cmdline_help();
      break;
    case -1:
      printf("End of options\\n");
      done = 1;
      break;
    case '?':
      printf("Error condition\\n");
      done = 1;
      break;
    default:
      printf("Unhandled %d (%c)\\n",ch,ch);
    }
  } while(!done);
  dump_cmdline_options();
}
"""
        return text

class Cmdline_Options :
    def __init__(self) :
        self.body = []
        self.dump = []
    def add(self,option) :
        text = """
  struct {
    uint8_t set;"""
        if 'flag' != option['type'] and 'switch' != option['type'] :
            text += """
    %s value;""" % (option['ctype'])
        text += """
  } %s;""" % (option['cname'])
        self.body.append(text)
        text = """
  if(cmdline_options.%s.set) {""" % (option['cname'])
        if 'flag' == option['type'] :
            text += """
    dump_flag("%s");""" % (option['cname'])
        elif 'switch' == option['type'] :
            text += """
    dump_switch("%s");""" % (option['cname'])
        else :
            text += """
    dump_%s("%s",cmdline_options.%s.value);""" % (option['type'],option['cname'],option['cname'])
        text += """
  }""" 
        self.dump.append(text)     
    def h_code(self) :
        text = """
struct cmdline_options {"""
        text += "".join(self.body)
        text += """
};

extern struct cmdline_options cmdline_options;
void cmdline_parse(int argc, char *argv[]);
"""
        return text
    def c_code(self) :
        text = """

struct cmdline_options cmdline_options;

void dump_cmdline_options(void) {"""
        text += "".join(self.dump)
        text += """
}
"""
        return text

class Cmdline_Help :
    def __init__(self) :
        self.body = []
    def add(self,option) :
        print(option)
        text = '--%s=<%s>' % (option['name'],option['type'])
        if option['lrel'] or option['rrel'] :
            lrel = option['lrel']
            rrel = option['rrel']
            text += '  Limits: '
            if lrel :
                text += '%s %s value ' % (lrel[0],lrel[1])
            if rrel :
                if not lrel :
                    text += 'value '
                text += '%s %s' % (rrel[0], rrel[1])
        self.body.append(text)
    def c_code(self) :
        text = """
void cmdline_help(void) {
  printf("Command-line Help\\n");
"""
        for line in self.body :
            text += '  printf("  %s\\n");\n' % (line)
        text += '}\n\n'
        return text
    
function_code = Function_Code()
cmdline_options = Cmdline_Options()
cmdline_help = Cmdline_Help()

for name in options :
    ctype = as_ctype(options[name]['type'])
    if None == ctype :
        has_arg = 0
    else :
        has_arg = 1
    options[name]['ctype'] = ctype
    cname = name.replace('-','_')
    options[name]['cname'] = cname
    enum = cname.upper()
    options[name]['enum'] = enum
    function_code.add(options[name])
    cmdline_options.add(options[name])
    cmdline_help.add(options[name])
    struct_option += format_struct_option % (name,has_arg,enum)
    enums += ', %s'%(enum)

struct_option += """  { .name = NULL, .has_arg = 0, .flag = NULL, .val = 0 }
};
"""

enums += """};
"""

fh = open('cmdline.c','w')
fh.write("""
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <getopt.h>
#include "cmdline.h"
""")
fh.write(support_code);
fh.write(cmdline_options.c_code())
fh.write(enums)
fh.write(struct_option % (len(options)+1))
fh.write(cmdline_help.c_code());
fh.write(function_code.render())
fh.close()

fh = open('cmdline.h','w')
fh.write("""
#include <stdint.h>
""")
fh.write(cmdline_options.h_code())
fh.close()
