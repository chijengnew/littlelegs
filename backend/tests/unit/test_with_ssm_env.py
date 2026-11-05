import pytest

from scripts.with_ssm_env import fetch_parameters, main, merged_env


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages
        self.kwargs = None

    def paginate(self, **kwargs):
        self.kwargs = kwargs
        return iter(self.pages)


class FakeSsm:
    def __init__(self, pages):
        self.paginator = FakePaginator(pages)

    def get_paginator(self, name):
        assert name == "get_parameters_by_path"
        return self.paginator


def params(*pairs):
    return {"Parameters": [{"Name": n, "Value": v} for n, v in pairs]}


def test_maps_direct_children_to_env_names_across_pages():
    ssm = FakeSsm(
        [
            params(("/littlelegs/prod/DATABASE_URL", "mysql+aiomysql://x")),
            params(("/littlelegs/prod/GOOGLE_SERVER_API_KEY", "k")),
        ]
    )
    assert fetch_parameters(ssm, "/littlelegs/prod/") == {
        "DATABASE_URL": "mysql+aiomysql://x",
        "GOOGLE_SERVER_API_KEY": "k",
    }
    assert ssm.paginator.kwargs == {"Path": "/littlelegs/prod", "Recursive": False, "WithDecryption": True}


@pytest.mark.parametrize("name", ["/littlelegs/prod/database_url", "/littlelegs/prod/A-B", "/other/prod/X"])
def test_rejects_invalid_or_foreign_names(name):
    with pytest.raises(SystemExit):
        fetch_parameters(FakeSsm([params((name, "v"))]), "/littlelegs/prod")


def test_parameter_store_values_override_existing_env():
    assert merged_env({"DATABASE_URL": "old", "APP_ENV": "production"}, {"DATABASE_URL": "new"}) == {
        "DATABASE_URL": "new",
        "APP_ENV": "production",
    }


def test_requires_command_after_separator():
    with pytest.raises(SystemExit):
        main(["--path", "/littlelegs/prod", "--"])
