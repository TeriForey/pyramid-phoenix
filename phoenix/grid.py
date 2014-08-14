import logging
logger = logging.getLogger(__name__)

from webhelpers.html.builder import HTML
from webhelpers.html.grid import Grid

from string import Template
from dateutil import parser as datetime_parser

from .utils import localize_datetime

class MyGrid(Grid):
    def __init__(self, request, *args, **kwargs):
        self.request = request
        if 'url' not in kwargs:
            kwargs['url'] = request.current_route_url
        super(MyGrid, self).__init__(*args, **kwargs)
        self.exclude_ordering = ['', 'action', '_numbered']
         #self.user_tz = u'US/Eastern'
        self.user_tz = u'UTC'

    def generate_header_link(self, column_number, column, label_text):
        """Override of the ObjectGrid to customize the headers. This is
        mostly taken from the example code in ObjectGrid itself.
        """
        GET = dict(self.request.copy().GET)
        self.order_column = GET.pop("order_col", None)
        self.order_dir = GET.pop("order_dir", None)
        # determine new order
        if column == self.order_column and self.order_dir == "desc":
            new_order_dir = "asc"
        else:
            new_order_dir = "desc"
        self.additional_kw['order_col'] = column
        self.additional_kw['order_dir'] = new_order_dir
        new_url = self.url_generator(_query=self.additional_kw)
        # set label for header with link
        label_text = HTML.tag("a", href=new_url, c=label_text)
        return super(MyGrid, self).generate_header_link(column_number,
                                                        column,
                                                        label_text)
    
    def default_header_column_format(self, column_number, column_name,
        header_label):
        """Override of the ObjectGrid to use <th> for header columns
        """
        if column_name == "_numbered":
            column_name = "numbered"
        if column_name in self.exclude_ordering:
            class_name = "c%s %s" % (column_number, column_name)
            return HTML.tag("th", header_label, class_=class_name)
        else:
            header_label = HTML(
                header_label, HTML.tag("span", class_="marker"))
            class_name = "c%s ordering %s" % (column_number, column_name)
            return HTML.tag("th", header_label, class_=class_name)

    def default_header_ordered_column_format(self, column_number, column_name,
                                             header_label):
        """Override of the ObjectGrid to use <th> and to add an icon
        that represents the sort order for the column.
        """
        icon_direction = self.order_dir == 'asc' and 'up' or 'down'
        icon_class = 'icon-chevron-%s' % icon_direction
        icon_tag = HTML.tag("i", class_=icon_class)
        header_label = HTML(header_label, " ", icon_tag)
        if column_name == "_numbered":
            column_name = "numbered"
        class_name = "c%s ordering %s %s" % (
            column_number, self.order_dir, column_name)
        return HTML.tag("th", header_label, class_=class_name)
        

    def __html__(self):
        """Override of the ObjectGrid to use a <thead> so that bootstrap
        renders the styles correctly
        """
        records = []
        # first render headers record
        headers = self.make_headers()
        r = self.default_header_record_format(headers)
        # Wrap the headers in a thead
        records.append(HTML.tag('thead', r))
        # now lets render the actual item grid
        for i, record in enumerate(self.itemlist):
            logger.debug('item %s %s', i, record)
            columns = self.make_columns(i, record)
            if hasattr(self, 'custom_record_format'):
                r = self.custom_record_format(i + 1, record, columns)
            else:
                r = self.default_record_format(i + 1, record, columns)
            records.append(r)
        return HTML(*records)

class ProcessesGrid(MyGrid):
    def __init__(self, request, *args, **kwargs):
        super(ProcessesGrid, self).__init__(request, *args, **kwargs)
        self.column_formats['action'] = self.action_td

    def action_td(self, col_num, i, item):
        """Generate the column that has the actions in it.
        """
        div = Template("""\
        <div class="btn-group">
            <button class="btn btn-mini btn-success execute" data-value="${identifier}">Execute</button>
        </div>
        """)
        return HTML.td(HTML.literal(div.substitute({'identifier': item.get('identifier')} )))
        

class OutputDetailsGrid(MyGrid):
    def __init__(self, request, *args, **kwargs):
        super(OutputDetailsGrid, self).__init__(request, *args, **kwargs)
        self.column_formats['reference'] = self.reference_td
        self.column_formats['action'] = self.action_td
        self.exclude_ordering = ['data', 'reference', 'action']

    def reference_td(self, col_num, i, item):
        """Generates the column with a download reference.
        """
        anchor = Template("""\
        <a class="reference" href="${reference}"><i class="icon-download"></i></a>
        """)
        return HTML.td(HTML.literal(anchor.substitute( {'reference': item.get('reference')} )))

    def action_td(self, col_num, i, item):
        """Generate the column that has the actions in it.
        """
        div = Template("""\
        <div class="btn-group">
            <button class="btn btn-mini btn-primary publish" data-value="${outputid}">Publish</button>
            <button class="btn btn-mini btn-primary view" data-value="${outputid}">View</button>
            <button class="btn btn-mini btn-primary mapit" data-value="${outputid}">MapIt</button>
        </div>
        """)
        return HTML.td(HTML.literal(div.substitute({'outputid': item.get('identifier')} )))

class JobsGrid(MyGrid):
    def __init__(self, request, *args, **kwargs):
        super(JobsGrid, self).__init__(request, *args, **kwargs)
        self.column_formats['creation_time'] = self.creation_time_td
        self.column_formats['status'] = self.status_td
        self.column_formats['status_message'] = self.message_td
        self.column_formats['status_location'] = self.status_location_td
        self.column_formats['progress'] = self.progress_td
        self.column_formats[''] = self.action_td
        self.exclude_ordering = ['status_message', 'action']

    def creation_time_td(self, col_num, i, item):
        if item.get('creation_time') is None:
            return HTML.td('')
        span_class = 'due-date badge'
        #if item.start_time:
        #    span_class += ' badge-important'
        creation_time = localize_datetime(item.get('creation_time'), self.user_tz)
        span = HTML.tag(
            "span",
            c=HTML.literal(creation_time.strftime('%Y-%m-%d %H:%M:%S')),
            class_=span_class,
        )
        return HTML.td(span)

    def status_td(self, col_num, i, item):
        """Generate the column for the job status.
        """
        status = item.get('status')
        if status is None:
            return HTML.td('')
        span_class = 'label'
        if status == 'ProcessSucceeded':
            span_class += ' label-success'
        elif status == 'ProcessFailed':
            span_class += ' label-warning'
        elif status == 'Exception':
            span_class += ' label-important'
        else:
            span_class += ' label-info'
            
        span = HTML.tag(
            "span",
            c=HTML.literal(status),
            class_=span_class,
            id_="status-%s" % item.get('identifier'))
        return HTML.td(span)

    def message_td(self, col_num, i, item):
        """Generates the column with job message.
        """
        message = item.get('status_message')
        #for error in item.get('errors'):
        #    message += ', Exception: %s' % str(error)
        span = HTML.tag(
            "span",
            c=HTML.literal(message),
            class_="",
            id_="message-%s" % item.get('identifier'))
        return HTML.td(span)

    def status_location_td(self, col_num, i, item):
        anchor = Template("""\
        <a class="reference" href="${url}"><i class="icon-download"></i></a>
        """)
        return HTML.td(HTML.literal(anchor.substitute( {'url': item.get('status_location')} )))

    def progress_td(self, col_num, i, item):
        """Generate the column for the job progress.
        """
        progress = item.get('progress', 100)
        if progress is None:
            return HTML.td('')
        span_class = 'progress progress-info bar'

        div_bar = HTML.tag(
            "div",
            c=HTML.literal(progress),
            class_="bar",
            style_="width: %d%s" % (progress, '%'),
            id_="progress-%s" % item.get('identifier'))
        div_progress = HTML.tag(
            "div",
            c=div_bar,
            class_="progress progress-info")
       
        return HTML.td(div_progress)
   
    def action_td(self, col_num, i, item):
        """Generate the column that has the actions in it.
        """
        div = Template("""\
        <div class="btn-group">
          <a class="btn dropdown-toggle" data-toggle="dropdown" href="#">Action<span class="caret"></span></a>
          <ul class="dropdown-menu">
            <!-- dropdown menu links -->
            <li><a class="show" data-value="${jobid}"><i class="icon-th-list"></i> Show Outputs</a></li>
            <li><a class="delete" data-value="${jobid}"><i class="icon-trash"></i> Delete</a></li>
          </ul>
        </div>
        """)
        return HTML.td(HTML.literal(div.substitute({'jobid': item.get('identifier')} )))

class UsersGrid(MyGrid):
    def __init__(self, request, *args, **kwargs):
        super(UsersGrid, self).__init__(request, *args, **kwargs)
        self.column_formats['activated'] = self.activated_td
        self.column_formats[''] = self.action_td
        self.exclude_ordering = ['notes', '']

    def activated_td(self, col_num, i, item):
        icon_class = "icon-thumbs-down"
        if item.get('activated') == True:
            icon_class = "icon-thumbs-up"
        div = Template("""\
        <a class="activate" data-value="${email}" href="#"><i class="${icon_class}"></i></a>
        """)
        return HTML.td(HTML.literal(div.substitute({'email': item['email'], 'icon_class': icon_class} )))

    def action_td(self, col_num, i, item):
        """Generate the column that has the actions in it.
        """
        div = Template("""\
        <div class="btn-group">
          <a class="btn dropdown-toggle" data-toggle="dropdown" href="#">Action<span class="caret"></span></a>
          <ul class="dropdown-menu">
            <!-- dropdown menu links -->
            <li><a class="edit" data-value="${email}"><i class="icon-pencil"></i> Edit</a></li>
            <li><a class="delete" data-value="${email}"><i class="icon-trash"></i> Delete</a></li>
          </ul>
        </div>
        """)
        return HTML.td(HTML.literal(div.substitute({'email': item.get('email')} )))

class CatalogGrid(MyGrid):
    def __init__(self, request, *args, **kwargs):
        super(CatalogGrid, self).__init__(request, *args, **kwargs)
        self.column_formats['title'] = self.title_td
        self.column_formats['format'] = self.format_td
        self.column_formats['modified'] = self.modified_td

    def title_td(self, col_num, i, item):
        tag_links = []
        for tag in item.get('subjects'):
            anchor = HTML.tag("a", href="#", c=tag, class_="label label-info")
            tag_links.append(anchor)
        
        div = Template("""\
        <div class="">
          <div class="">
            <h3 class="">${title}</h3>
            <div>${abstract}</div>
          </div>
          <div>${tags}</div>
        </div>
        """)
        return HTML.td(HTML.literal(div.substitute( {'title': item['title'], 'abstract': item['abstract'], 'tags': ' '.join(tag_links)} )))

    def format_td(self, col_num, i, item):
        format = item.get('format')
        span_class = 'label'
        if 'wps' in format.lower():
            span_class += ' label-warning'
        elif 'wms' in format.lower():
            span_class += ' label-info'
        elif 'netcdf' in format.lower():
            span_class += ' label-success'
        else:
            span_class += ' label-default'
        anchor = Template("""\
        <a class="${span_class}" href="${source}" data-format="${format}">${format}</a>
        """)
        return HTML.td(HTML.literal(anchor.substitute(
            {'source': item['source'], 'span_class': span_class, 'format': format} )))

    def modified_td(self, col_num, i, item):
        if item.get('modified') is None:
            return HTML.td('')
        span_class = 'due-date badge'
        #if item.start_time:
        #    span_class += ' badge-important'
        creation_time = datetime_parser.parse(item.get('modified'))
        span = HTML.tag(
            "span",
            c=HTML.literal(creation_time.strftime('%Y-%m-%d %H:%M:%S')),
            class_=span_class,
        )
        return HTML.td(span)

class CatalogSearchGrid(CatalogGrid):
    def __init__(self, request, *args, **kwargs):
        super(CatalogSearchGrid, self).__init__(request, *args, **kwargs)
        self.column_formats['selected'] = self.selected_td

    def selected_td(self, col_num, i, item):
        """Generate the column for selecting items.
        """
        icon_class = "icon-thumbs-down"
        if item['selected'] == True:
            icon_class = "icon-thumbs-up"
        div = Template("""\
        <button class="btn btn-mini select" data-value="${identifier}"><i class="${icon_class}"></i></button>
        """)
        return HTML.td(HTML.literal(div.substitute({'identifier': item['identifier'], 'icon_class': icon_class} )))

class CatalogSettingsGrid(CatalogGrid):
    def __init__(self, request, *args, **kwargs):
        super(CatalogSettingsGrid, self).__init__(request, *args, **kwargs)
        self.column_formats[''] = self.action_td

    def action_td(self, col_num, i, item):
        div = Template("""\
        <div class="btn-group">
          <a class="btn dropdown-toggle" data-toggle="dropdown" href="#">Action<span class="caret"></span></a>
          <ul class="dropdown-menu">
            <!-- dropdown menu links -->
            <li><a class="edit" data-value="${identifier}"><i class="icon-pencil"></i> Edit</a></li>
            <li><a class="delete" data-value="${identifier}"><i class="icon-trash"></i> Delete</a></li>
          </ul>
        </div>
        """)
        return HTML.td(HTML.literal(div.substitute({'identifier': item.get('identifier')} )))
       

