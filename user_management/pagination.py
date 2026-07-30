from rest_framework.pagination import PageNumberPagination


class PageNumberLimitPagination(PageNumberPagination):
    page_size_query_param = 'limit'  # Optional: customize the query param name
    max_page_size = 100  # Set the maximum allowed page size