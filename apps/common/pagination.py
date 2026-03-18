from rest_framework.pagination import PageNumberPagination


class StandardResultsPagination(PageNumberPagination):
    """
    Generic pagination class for all API list endpoints.

    Supports:
    - ?page=N      — navigate to page N
    - ?page_size=N — override page size (max 100)
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
