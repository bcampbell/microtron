__import__('pkg_resources').declare_namespace(__name__)

import isodate, re, os
import lxml.etree
import datetime
import pytz

class ParseError(Exception):
    def __init__(self, message, sourceline=None):
        Exception.__init__(self, message)
        self.sourceline = sourceline

class Parser(object):
    def __init__(self, tree, formats=None, strict=False, collect_errors=False):
        """set up parser

        tree    -- the document that we are going to parse
        formats -- the microformat definitions (if None, load from mf.xml)
        strict  -- if True, parser will be in pedantic try-to-follow-the-specs mode.
                   if False, parser aims to be loose enough for real-world use
        collect_errors -- collect parsing errors rather than raising them
                   as exceptions, and try to continue parsing
        """
        self.root = tree
        self.formats = formats
        self.strict = strict
        self.collect_errors = collect_errors
        self.errors = []
        if formats is None:
            path = os.path.abspath(os.path.dirname(__file__))
            fname = os.path.join(path, 'mf.xml')
            self.formats = lxml.etree.parse(fname)

    def parse_format(self, mf, root=None):
        root = root if root is not None else self.root
        format = self.formats.xpath('/microformats/*[@name="%s"] | /microformats/%s' % (mf, mf))
        if not format:
            raise Exception( "unknown format '%s'" % (mf) )
        else:
            format = format[0]

        results = []
        if format.attrib['type'] == 'compound':
            expr = 'descendant-or-self::*[contains(concat(" ", normalize-space(@class), " "), " %s ")]' % format.tag
            for node in root.xpath(expr):
                results.append(self._parse_node(node, format))

        elif format.attrib['type'] == 'elemental':
            for feature in format:
                attribute = feature.attrib['attribute']
                value = feature.tag
                expr = 'descendant-or-self::*[contains(concat(" ", normalize-space(@%s), " "), " %s ")]' % (attribute, value)

                for node in root.xpath(expr):
                    results.append({'__type__': mf, 'value': value, 'href': node.attrib['href'], 'text': node.text})

        return results

    def _parse_node(self, node, format):
        result = {'__type__': format.tag}
        for prop in format:
            prop_name = prop.tag
            prop_type = prop.attrib['type'] if 'type' in prop.attrib else 'text'
            prop_mandatory = True if 'mandatory' in prop.attrib and prop.attrib['mandatory'] == 'yes' else False
            prop_attr = prop.attrib['attribute'] if 'attribute' in prop.attrib else 'class'
            prop_many = prop.attrib['many'] if 'many' in prop.attrib else False
            prop_couldbe = prop.attrib['couldbe'].split('|') if 'couldbe' in prop.attrib else []
            prop_values = set(prop.attrib['values'].split(',')) if 'values' in prop.attrib else None
            prop_separator = prop.attrib['separator'] if 'separator' in prop.attrib else ""
            
            # Select all properties, but exclude nested properties
            prop_expr = 'descendant-or-self::*[contains(concat(" ", normalize-space(@%s), " "), " %s ")]' % (prop_attr, prop_name)
            parent_expr = 'ancestor::*[contains(concat(" ", normalize-space(@class), " "), " %s ")]' % format.tag
            prop_nodes = [prop_node for prop_node in node.xpath(prop_expr) if prop_node.xpath(parent_expr)[0] == node]

            # missing something required?
            if self.strict and not prop_nodes and prop_mandatory:
                err = ParseError("missing mandatory %s property: %s" % (format.tag, prop_name), node.sourceline)
                if self.collect_errors:
                    self.errors.append(err)
                    continue
                else:
                    raise err

            if prop_many == 'many':
                values = []
            elif prop_many == 'manyasone':
                values = ""

            # for each node matching the property we're looking for...
            for prop_node in prop_nodes:
                try:
                    # Check if this prop_node is one or more of the possible "could be" formats
                    value = {}
                    for mf in prop_couldbe:
                        try:
                            format_results = self.parse_format(mf, prop_node)
                            if format_results and len(format_results[0]) > 1:
                                if '__type__' in value:
                                    value['__type__'] += ' ' + format_results[0].pop('__type__')

                                value.update(format_results[0])

                        except:
                            pass

                    # Check if this property is a compound property
                    if len(prop):
                        try:
                            prop_result = self._parse_node(prop_node, prop)
                            if len(prop_result) > 1:
                                if '__type__' in value:
                                    value['__type__'] += ' ' + prop_result.pop('__type__')

                                value.update(prop_result)
                        except:
                            pass

                    if not value:
                        value['__type__'] = prop_type
                        value['__srcline__'] = prop_node.sourceline

                        if prop_type == 'text':
                            value = self._parse_value(prop_node)

                        elif prop_type in ('url', 'email'):
                            value['text'] = self._parse_text(prop_node)
                            if 'href' in prop_node.attrib:
                                value['href'] = prop_node.attrib['href']
                                for prefix in ('mailto', 'tel', 'fax', 'modem'):
                                    if value['href'].lower().startswith(prefix + ':'):
                                        value[prefix] = value['href'][len(prefix + ':'):]
                                        break

                        elif prop_type == 'image':
                            if 'title' in prop_node.attrib:
                                value['title'] = prop_node.attrib['title']

                            if 'alt' in prop_node.attrib:
                                value['alt'] = prop_node.attrib['alt']

                            if 'src' in prop_node.attrib:
                                value['src'] = prop_node.attrib['src']

                        elif prop_type == 'object':
                            value['text'] = self._parse_text(prop_node)
                            if 'data' in prop_node.attrib:
                                value['data'] = prop_node.attrib['data']

                        elif prop_type == 'date':
                            value['text'] = self._parse_text(prop_node)
                            # TODO: do we need a date-specific parsing fn which barfs if a time is included?
                            value['date'] = self._parse_datetime_value(prop_node)

                        elif prop_type == 'datetime':
                            value['text'] = self._parse_text(prop_node)
                            value['datetime'] = self._parse_datetime_value(prop_node)

                        else:
                            # Try to parse this property as a sub-format
                            results = self.parse_format(prop_type, prop_node)
                            if results and len(results[0]) > 1:
                                value = results[0]
                            else:
                                raise Exception("Could not parse expected format: '%s'" % (prop_type,))

                # TODO: revamp exception handling - BenC
                # this isn't the place to catch/collect the errors. they should
                # be caught further down, where the code is better able to
                # continue parsing.
                except Exception, e:
                    if self.strict:
                        err = ParseError("Error parsing value for property '%s': %s" % (prop_name, e), sourceline=prop_node.sourceline)
                        if self.collect_errors:
                            self.errors.append(err)
                            continue    # go on to next property
                        else:
                            raise err
                    else:
                        value = self._parse_value(prop_node)

                # Convert the value to a string (if it isn't one already)
                if isinstance(value, basestring):
                    value_text = value
                elif 'text' in value:
                    value_text = value['text']
                else:
                    value_text = ""

                if self.strict and prop_values and value_text.lower() not in prop_values:
                    err = ParseError("Invalid value for property '%s': %s" % (prop_name, value))
                    if self.collect_errors:
                        self.errors.append(err)
                        continue    # go on to next property
                    else:
                        raise err

                if prop_many == 'many':
                    values.append(value)

                elif prop_many == 'manyasone':
                    if value_text:
                        if values and prop_separator:
                            values += prop_separator

                        values += value_text

                else:
                    result[prop_name] = value
                    break

            if prop_many and values:
                result[prop_name] = values

        return result



    def _find_value_nodes(self, node):
        """ find child value nodes, according to value-class-pattern """
        # look for class="value" and class="value-title"
        # TODO: bug: this will pick up nested "value" elements.
        #       value-class-pattern says that nested values shouldn't be used
        value_expr = 'descendant::*[contains(concat(" ", normalize-space(@class), " "), " value ")] | descendant::*[contains(concat(" ", normalize-space(@class), " "), " value-title ")]'
        return node.xpath(value_expr)




    def _parse_value(self, node):
        """ get a value from a node, handling (optional) value-class-pattern """

        value_nodes = self._find_value_nodes(node)
        if not value_nodes:
            # no value-class-pattern - just use element itself as value
            return self._get_value_frag(node)
        return "".join( [self._get_value_frag(n) for n in value_nodes] )



    def _parse_datetime_value(self, node):
        """ get a datetime value from a node, handling (optional) value-class-pattern """

        value_nodes = self._find_value_nodes(node)

        if not value_nodes:
            # no value-class-pattern - just use element itself
            # try for full isodate, then just date
            txt = self._get_value_frag(node).strip()
            dt = self._eval_as_datetime(txt)
            if dt is None:
                dt = self._eval_as_date(txt)
            return dt

        date_part = None
        time_part = None
        tzinfo_part = None
        for n in value_nodes:
            txt = self._get_value_frag(n).strip()

            # try bare timezone
            obj = self._eval_as_tzinfo(txt)
            if obj is not None:
                if tzinfo_part is None:
                    tzinfo_part = obj
                else:
                    pass # should warn about multiple times in strict mode?
                continue

            # try time (+optional timezone)
            obj = self._eval_as_time(txt)
            if obj is not None:
                if time_part is None:
                    time_part = obj
                else:
                    pass # should warn about multiple times in strict mode?
                continue

            # try bare date
            obj = self._eval_as_date(txt)
            if obj is not None:
                if date_part is None:
                    date_part = obj
                else:
                    pass # should warn about multiple times in strict mode?
                continue


            # if we get this far we've not been able use fragment as part of
            # a datetime...
            if self.strict:
                err = ParseError("Bad datetime value '%s'" % (txt), sourceline=n.sourceline)
                if self.collect_errors:
                   self.errors.append(err)
                else:
                   raise err

        # now assemble the fragments we've accumulated
        if time_part is None:
            time_part = datetime.time(0,0,0,0,tzinfo_part)
        if date_part is None:
            raise Exception("missing date")
        return datetime.datetime.combine(date_part, time_part)






    def _get_value_frag(self, n):
        """ get a value fragment from a single element """

        if n.tag =='abbr' or ('value-title' in n.attrib['class']):
            # value is in title attr.
            if 'title' in n.attrib:
                return n.attrib['title']
            else:
                if self.strict:
                    err = ParseError("missing required 'title' attr on '%s' value element" % (n.tag), sourceline=n.sourceline)
                    if self.collect_errors:
                        self.errors.append(err)
                        return ''   # just to allow parsing to continue
                    else:
                       raise err
                else:
                    return ''

        if n.tag in ('img','area'):
            if 'alt' in n.attrib:
                return n.attrib['alt']
            else:
                if self.strict:
                    err = ParseError("missing required 'alt' attr on '%s' value element" % (n.tag), sourceline=n.sourceline)
                    if self.collect_errors:
                        self.errors.append(err)
                        return ''   # just to allow parsing to continue
                    else:
                       raise err
                else:
                    return ''

        # user inner text as value
        return self._parse_text(n)



    def _parse_text(self, node):
        text_expr = 'normalize-space(string(.))'
        return node.xpath(text_expr)


    def _eval_as_tzinfo(self, txt):
        """try and parse a timezone, as per value-class-pattern rules"""

        tzpat = r'^(?P<tzname>(?:(?P<tzsign>[-+])(?:(?P<tzhour>\d{1,2})[:]?(?P<tzmin>\d\d)))|(?P<tzzulu>Z))$'

        m = re.compile(tzpat,re.IGNORECASE).match(txt)
        if m:
            return self._compose_tzinfo( m.groupdict() )
        # TODO: special case for timezones "-XX" "+XX"
        return None



    def _eval_as_time(self, txt):
        """try and parse a time, as per value-class-pattern rules""" 

        timepat = r'(?P<hour>\d{1,2})[:](?P<min>\d\d)(?:[:](?P<sec>\d\d))?'
        ampmpat = r'(?:(?P<am>am|a[.]m[.])|(?P<pm>pm|p[.]m[.]))'
        tzpat = r'(?P<tzname>(?:(?P<tzsign>[-+])(?:(?P<tzhour>\d{1,2})[:]?(?P<tzmin>\d\d)))|(?P<tzzulu>Z))'

        # looking for time or time+timezone
        m = re.compile("^"+timepat+ampmpat+"?"+tzpat+"?$",re.IGNORECASE).match(txt)
        if m:
            return self._compose_time(m.groupdict())

        # special case for HHam and HHpm
        m = re.compile(r'^(?P<hour>\d{1,2})'+ampmpat+r'?$',re.IGNORECASE).match(txt)
        if m:
            return self._compose_time(m.groupdict())
        return None



    def _eval_as_date(self, txt):
        """try and parse a date, as per value-class-pattern rules""" 
        datepat = r'^(?P<year>\d\d\d\d)-(?P<month>\d\d)-(?P<day>\d\d)$' # YYYY-MM-DD
        m = re.compile( datepat, re.IGNORECASE ).match(txt)
        if m:
            return self._compose_date(m.groupdict())

        orddatepat = r'^(?P<year>\d\d\d\d)-(?P<ordinalday>\d\d\d)$' # YYYY-DDD   -Ordinal date
        m = re.compile( orddatepat, re.IGNORECASE ).match(txt)
        if m:
            return self._compose_date(m.groupdict())

        return None


    def _eval_as_datetime(self,txt):
        parts = txt.split('T')
        if len(parts) != 2:
            return None
        date = self._eval_as_date(parts[0])
        time = self._eval_as_time(parts[1])
        if date is None or time is None:
            return None
        return datetime.datetime.combine( date, time )


    def _compose_tzinfo(self, g):
        """build a tzinfo from extracted parts"""
        if g.get('tzname') is None:
            return None

        if g['tzzulu'] is not None:
            tzinfo = isodate.tzinfo.Utc()
        else:
            tzsign = ((g['tzsign'] == '-') and -1) or 1
            tzhour = int(g['tzhour'])
            tzmin = 0
            if g['tzmin']:
                tzmin = int(g['tzmin'])
            tzinfo = isodate.tzinfo.FixedOffset(tzsign*tzhour, tzsign*tzmin, g['tzname'])
        return tzinfo



    def _compose_time(self,g):
        """build a time object from extracted parts"""
        # get time
        hour = int(g['hour'])

        min=0
        if g.get('min') is not None:
            min = int(g['min'])

        sec=0
        if g.get('sec') is not None:
            sec = int( g['sec'] )

        if g['am'] is not None:
            if hour==12:
                hour = 0
        elif g['pm'] is not None:
            if hour < 12:
                hour += 12
        if hour==24:
            hour = 0

        # get timezone, if any
        tzinfo = self._compose_tzinfo(g)

        return datetime.time(hour, min, sec, 0, tzinfo )

    def _compose_date(self,g):
        """build a date object from extracted parts"""
        if 'month' in g:
            return datetime.date(int(g['year']), int(g['month']), int(g['day']))
        else:
            # ordinal date YYYY-DDD
            return datetime.date(int(g['year']),1,1 ) + datetime.timedelta(days=int(g['ordinalday'])-1)


