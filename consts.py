"""
This dictionary maps each character to its frequency as the first letter in an english word. It is calculated by
multiplying the frequency with the total character count of 26. This results in scores around 1, with scores below 1
meaning that this character occurs less than average as the first character, and scores above 1 meaning that this
character occurs more than average as the first character.
"""
FIRST_CHAR_SCORE = {
    "a": 1.7855527485443319,
    "b": 1.293519406654868,
    "c": 2.25552748544332,
    "d": 1.3159995136515314,
    "e": 0.9973439969738318,
    "f": 0.8354872265978572,
    "g": 0.7694519122951594,
    "h": 0.965450345172316,
    "i": 0.9272341632779886,
    "j": 0.1995109495953851,
    "k": 0.2776293214087894,
    "l": 0.7026438443144513,
    "m": 1.3913078720903527,
    "n": 0.9454992502127775,
    "o": 0.8908444900771402,
    "p": 2.4489266559489877,
    "q": 0.12595884951567798,
    "r": 1.1790113616406155,
    "s": 2.7231839613082776,
    "t": 1.3220410424068847,
    "u": 1.5993893624782156,
    "v": 0.37436403182880534,
    "w": 0.46077194309722913,
    "x": 0.03561691952283812,
    "y": 0.08029613217870604,
    "z": 0.09743721376366166
}

"""Amount of karma subtracted for a mistake """
MISTAKE_PENALTY = 10

"""Minimum karma needed for the reliable role """
RELIABLE_ROLE_KARMA_THRESHOLD = 50

"""Minimum accuracy needed for the reliable role """
RELIABLE_ROLE_ACCURACY_THRESHOLD = .99

'''The bot's config file'''
CONFIG_FILE: str = 'config_word_chain.json'

'''The bot's database file'''
DB_FILE: str = 'database_word_chain.sqlite3'

"""
A dictionary mapping the country name to the corresponding flag emoji.
"""
COUNTRY_FLAGS = {
    'afghanistan': '🇦🇫',
    'albania': '🇦🇱',
    'algeria': '🇩🇿',
    'andorra': '🇦🇩',
    'angola': '🇦🇴',
    'anguilla': '🇦🇮',
    'antarctica': '🇦🇶',
    'antigua': '🇦🇬',
    'barbuda': '🇦🇬',
    'argentina': '🇦🇷',
    'armenia': '🇦🇲',
    'aruba': '🇦🇼',
    'australia': '🇦🇺',
    'austria': '🇦🇹',
    'azerbaijan': '🇦🇿',
    'bahamas': '🇧🇸',
    'bahrain': '🇧🇭',
    'bangladesh': '🇧🇩',
    'barbados': '🇧🇧',
    'belarus': '🇧🇾',
    'belgium': '🇧🇪',
    'belize': '🇧🇿',
    'benin': '🇧🇯',
    'bermuda': '🇧🇲',
    'bhutan': '🇧🇹',
    'bolivia': '🇧🇴',
    'bonaire': '🇧🇶',
    'bosnia': '🇧🇦',
    'herzegovina': '🇧🇦',
    'botswana': '🇧🇼',
    'bouvet': '🇧🇻',
    'brazil': '🇧🇷',
    'brunei': '🇧🇳',
    'bulgaria': '🇧🇬',
    'burkina': '🇧🇫',
    'burundi': '🇧🇮',
    'cambodia': '🇰🇭',
    'cameroon': '🇨🇲',
    'canada': '🇨🇦',
    'cayman': '🇰🇾',
    'chad': '🇹🇩',
    'chile': '🇨🇱',
    'china': '🇨🇳',
    'colombia': '🇨🇴',
    'comoros': '🇰🇲',
    'congo': '🇨🇩',
    'croatia': '🇭🇷',
    'cuba': '🇨🇺',
    'cyprus': '🇨🇾',
    'czechia': '🇨🇿',
    'denmark': '🇩🇰',
    'djibouti': '🇩🇯',
    'dominica': '🇩🇲',
    'dominican': '🇩🇴',
    'ecuador': '🇪🇨',
    'egypt': '🇪🇬',
    'salvador': '🇸🇻',
    'eritrea': '🇪🇷',
    'estonia': '🇪🇪',
    'eswatini': '🇸🇿',
    'ethiopia': '🇪🇹',
    'fiji': '🇫🇯',
    'finland': '🇫🇮',
    'france': '🇫🇷',
    'gabon': '🇬🇦',
    'gambia': '🇬🇲',
    'georgia': '🇬🇪',
    'germany': '🇩🇪',
    'ghana': '🇬🇭',
    'gibraltar': '🇬🇮',
    'greece': '🇬🇷',
    'greenland': '🇬🇱',
    'grenada': '🇬🇩',
    'guadeloupe': '🇬🇵',
    'guam': '🇬🇺',
    'guatemala': '🇬🇹',
    'guernsey': '🇬🇬',
    'guinea': '🇬🇳',
    'guinea-bissau': '🇬🇼',
    'guyana': '🇬🇾',
    'haiti': '🇭🇹',
    'vatican': '🇻🇦',
    'honduras': '🇭🇳',
    'hungary': '🇭🇺',
    'iceland': '🇮🇸',
    'india': '🇮🇳',
    'bharat': '🇮🇳',
    'indonesia': '🇮🇩',
    'iran': '🇮🇷',
    'iraq': '🇮🇶',
    'ireland': '🇮🇪',
    'israel': '🇮🇱',
    'italy': '🇮🇹',
    'jamaica': '🇯🇲',
    'japan': '🇯🇵',
    'jersey': '🇯🇪',
    'jordan': '🇯🇴',
    'kazakhstan': '🇰🇿',
    'kenya': '🇰🇪',
    'kiribati': '🇰🇮',
    'korea': '🇰🇷',
    'kuwait': '🇰🇼',
    'kyrgyzstan': '🇰🇬',
    "laos": '🇱🇦',
    'latvia': '🇱🇻',
    'lebanon': '🇱🇧',
    'lesotho': '🇱🇸',
    'liberia': '🇱🇷',
    'libya': '🇱🇾',
    'liechtenstein': '🇱🇮',
    'lithuania': '🇱🇹',
    'luxembourg': '🇱🇺',
    'macao': '🇲🇴',
    'madagascar': '🇲🇬',
    'malawi': '🇲🇼',
    'malaysia': '🇲🇾',
    'maldives': '🇲🇻',
    'mali': '🇲🇱',
    'malta': '🇲🇹',
    'martinique': '🇲🇶',
    'mauritania': '🇲🇷',
    'mauritius': '🇲🇺',
    'mayotte': '🇾🇹',
    'mexico': '🇲🇽',
    'micronesia': '🇫🇲',
    'moldova': '🇲🇩',
    'monaco': '🇲🇨',
    'mongolia': '🇲🇳',
    'montenegro': '🇲🇪',
    'montserrat': '🇲🇸',
    'morocco': '🇲🇦',
    'mozambique': '🇲🇿',
    'myanmar': '🇲🇲',
    'namibia': '🇳🇦',
    'nauru': '🇳🇷',
    'nepal': '🇳🇵',
    'netherlands': '🇳🇱',
    'caledonia': '🇳🇨',
    'zealand': '🇳🇿',
    'nicaragua': '🇳🇮',
    'niger': '🇳🇪',
    'nigeria': '🇳🇬',
    'niue': '🇳🇺',
    'norfolk': '🇳🇫',
    'macedonia': '🇲🇰',
    'norway': '🇳🇴',
    'oman': '🇴🇲',
    'pakistan': '🇵🇰',
    'palau': '🇵🇼',
    'palestine': '🇵🇸',
    'panama': '🇵🇦',
    'papua new guinea': '🇵🇬',
    'paraguay': '🇵🇾',
    'peru': '🇵🇪',
    'philippines': '🇵🇭',
    'pitcairn': '🇵🇳',
    'poland': '🇵🇱',
    'portugal': '🇵🇹',
    'puerto': '🇵🇷',
    'qatar': '🇶🇦',
    'romania': '🇷🇴',
    'rwanda': '🇷🇼',
    'samoa': '🇼🇸',
    'arabia': '🇸🇦',
    'saudi': '🇸🇦',
    'senegal': '🇸🇳',
    'serbia': '🇷🇸',
    'seychelles': '🇸🇨',
    'singapore': '🇸🇬',
    'slovakia': '🇸🇰',
    'slovenia': '🇸🇮',
    'solomon': '🇸🇧',
    'somalia': '🇸🇴',
    'spain': '🇪🇸',
    'lanka': '🇱🇰',
    'sudan': '🇸🇩',
    'suriname': '🇸🇷',
    'sweden': '🇸🇪',
    'switzerland': '🇨🇭',
    'syria': '🇸🇾',
    'taiwan': '🇹🇼',
    'tajikistan': '🇹🇯',
    'tanzania': '🇹🇿',
    'thailand': '🇹🇭',
    'timor-leste': '🇹🇱',
    'togo': '🇹🇬',
    'tokelau': '🇹🇰',
    'tonga': '🇹🇴',
    'trinidad': '🇹🇹',
    'tobago': '🇹🇹',
    'tunisia': '🇹🇳',
    'turkmenistan': '🇹🇲',
    'tuvalu': '🇹🇻',
    'turkey': '🦃',
    'uganda': '🇺🇬',
    'ukraine': '🇺🇦',
    'emirates': '🇦🇪',
    'uk': '🇬🇧',
    'britain': '🇬🇧',
    'usa': '🇺🇸',
    'america': '🇺🇸',
    'uruguay': '🇺🇾',
    'uzbekistan': '🇺🇿',
    'vanuatu': '🇻🇺',
    'venezuela': '🇻🇪',
    'vietnam': '🇻🇳',
    'yemen': '🇾🇪',
    'zambia': '🇿🇲',
    'zimbabwe': '🇿🇼'
}
