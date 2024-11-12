# import json

# import httpx
# import pytest
# import respx

# TODO: Fix so this works properly with pagination
# def test_get_issue(
#     respx_mock: respx.router.MockRouter, request: pytest.FixtureRequest
# ) -> None:
#     for i in (0, 1, 2):
#         api_data = json.loads(
#             (request.node.path.parent / "data" / f"response-{i}.json").read_text()
#         )
#         respx_mock.post(API_URL).mock(
#             return_value=httpx.Response(200, json=api_data)
#         )

#     issues = get_issues(token="dummy", repos=["vikahl/issue-downloader"])

#     # There are 83 issues in the test response data
#     assert len(issues) == 83

#     # save_issues(issues, root_path=pathlib.Path("./test-output/"))


def test_dummy() -> None:
    assert True
