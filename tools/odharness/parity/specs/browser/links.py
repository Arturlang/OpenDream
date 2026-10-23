"""Browser suite: byond://? links from the page, as DM parses them into href and href_list."""


def build(s):
    s.browser()
    L = s.link

    # Spaces and plus
    L("space %20", '"a=x%20y"')
    L("space plus", '"a=x+y"')
    L("raw space", '"a=x y"')
    L("plus in key", '"a+b=1"')
    L("%20 in key", '"a%20b=1"')

    # Encoded reserved characters
    L("encoded plus semicolon amp percent", '"a=%2B&b=%3B&c=%26&d=%25"')
    L("encoded equals", '"a=x%3Dy&b%3Dc=2"')
    L("encoded hash question", '"a=%23x%3Fy"')
    L("encoded misc punctuation", '"a=%7E%21%40%24%5E%2A%28%29%27%22"')
    L("encoded control chars", '"a=x%09y%0Az%0Dw"')
    L("encodeURIComponent specials", '"a=" + encodeURIComponent("<>\\"\' &;=+%#?/")')
    L("lower case hex", '"a=%2b%3b%c3%a9"')

    # Unicode
    L("unicode encoded", '"u=%C3%A9"')
    L("emoji encoded", '"u=%F0%9F%98%80"')
    L("unicode encodeURIComponent", '"u=" + encodeURIComponent("é中\U0001F600")')
    L("raw unicode", '"u=é中"')
    L("iso latin1 byte", '"u=%E9"')
    L("percent u form", '"u=%u00e9"')

    # Invalid percent sequences
    L("lone percent", '"a=%"')
    L("percent zz", '"a=%zz"')
    L("percent one digit", '"a=%4"')
    L("truncated utf8", '"a=%C3"')
    L("byte FF", '"a=%FF"')

    # Separators
    L("semicolon separator", '"a=1;b=2"')
    L("mixed separators", '"a=1;b=2&c=3"')
    L("double ampersand", '"a=1&&b=2"')
    L("trailing ampersand", '"a=1&"')
    L("equals in value", '"a=b=c"')
    L("fragment", '"a=1#frag"')

    # Repeated keys
    L("repeated key two", '"k=1&k=2"')
    L("repeated with empty", '"k=&k=2"')
    L("repeated semicolon", '"k=1;k=2"')

    # Keys without values and empty keys
    L("key only", '"flag"')
    L("key with equals no value", '"flag="')
    L("several bare keys", '"a&b&c"')
    L("empty key", '"=v"')
    L("lone ampersand", '"&"')

    # Key case
    L("key case", '"Key=1&key=2&KEY=3"')

    # Long hrefs
    L("long value 2000", '"long=" + "x".repeat(2000)')
    L("long value 8000", '"long=" + "x".repeat(8000)')
    L("many keys 200", 'Array.from({length: 200}, function (_, i) { return "k" + i + "=" + i; }).join("&")')
