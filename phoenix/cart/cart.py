class CartItem(object):
    def __init__(self, url, title=None, abstract=None, mime_type=None, dataset=None):
        self.url = url
        self._title = title
        self._abstract = abstract
        self.mime_type = mime_type or 'application/x-netcdf'
        self.dataset = dataset

    @property
    def title(self):
        return self._title or self.filename

    @property
    def abstract(self):
        return self._abstract or "No Summary"

    @property
    def filename(self):
        return self.url.split('/')[-1]

    def is_service(self):
        return self.is_opendap() or self.is_thredds_catalog()

    def is_opendap(self):
        return self.mime_type == 'application/x-ogc-dods'

    def is_thredds_catalog(self):
        return self.mime_type == 'application/x-thredds-catalog'

    def to_json(self):
        return dict(url=self.url, title=self._title, abstract=self._abstract,
                    mime_type=self.mime_type, dataset=self.dataset)


class Cart(object):

    def __init__(self, request):
        self.request = request
        self.session = request.session
        # TODO: loading stored items needs to be improved
        self.items = None
        self.load()

    def __iter__(self):
        """
        Allow the cart to be iterated giving access to the cart's items.
        """
        for key in self.items:
            yield self.items[key]

    def __contains__(self, url):
        """
        Returns: True if cart item with given url is in cart, otherwise False.
        """
        return url in self.items

    def add_item(self, url, title=None, abstract=None, mime_type=None):
        """
        Add cart item.
        """
        if url and self.request.has_permission('edit'):
            item = CartItem(url, title=title, abstract=abstract, mime_type=mime_type)
            self.items[url] = item
            self.save()
        else:
            item = None
        return item

    def remove_item(self, url):
        """
        Remove cart item with given url.
        """
        if url and url in self.items:
            item = self.items[url]
            del self.items[url]
            self.save()
        else:
            item = None
        return item

    def count(self):
        """
        Returns: number of cart items.
        """
        return len(self.items)

    def has_items(self):
        """
        Returns: True if cart items available, otherwise False.
        """
        return self.count() > 0

    def clear(self):
        """
        Removes all items of cart and updates session.
        """
        self.items = {}
        self.session['cart'] = []
        self.session.changed()

    def save(self):
        """
        Store cart items in session.
        """
        self.session['cart'] = self.to_json()
        self.session.changed()

    def load(self):
        """
        Load cart items from session.
        """
        items_as_json = self.session.get('cart')
        self.items = {}
        if items_as_json:
            for item in items_as_json:
                self.items[item['url']] = CartItem(**item)

    def to_json(self):
        """
        Returns: json representation of all cart items.
        """
        return [self.items[key].to_json() for key in self.items]
