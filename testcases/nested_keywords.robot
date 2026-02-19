*** Test Cases ***
Nested Passing Test Case
    Level One Keyword

Nested Failing Test Case
    Level Two Keyword    should_fail=${True}

Nested Warning Test Case
    Level Two Keyword    should_warn=${True}    should_fail=${True}

*** Keywords ***
Level One Keyword
    Log    In the level one keyword
    Level Two Keyword

Level Two Keyword
    [Arguments]    ${should_fail}=${False}    ${should_warn}=${False}
    Log    In the level two keyword
    Level Three Keyword
    IF    ${should_warn}
        Warning Keyword
    END
    IF    ${should_fail}
        Failing Keyword
    END

Level Three Keyword
    Log    In the level three keyword

Failing Keyword
    Log    In the failing keyword
    Fail    This keyword failed

Warning Keyword
    Log    In the warning keyword
    LOG    This keyword warned    level=WARN
