"""Check complete route bundles for repeated content, dead links and unknown names."""
from collections import Counter
import hashlib
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / 'skills/logic-writing'
LINKS = re.compile(r'\[[^\]]*\]\(([^\s)]+)\)')
CODES = re.compile(r'`([^`\n]+)`')


def _destination(origin, link):
    value = urlsplit(link)
    if value.scheme or value.netloc:
        return None
    path = (origin.parent / unquote(value.path)).resolve() if value.path else origin
    return path, unquote(value.fragment)


def _slug(heading):
    return "".join(
        char for char in heading.lower() if char.isalnum() or char.isspace() or char == "-"
    ).replace(" ", "-")


def _check(route, files, help_options):
    paragraphs = Counter(
        " ".join(part.split())
        for path in files
        for part in re.split(r"\n\s*\n", path.read_text())
        if len(part.split()) >= 8 and not re.fullmatch(r"#+ [^\n]+", part.strip())
    )
    for paragraph, count in paragraphs.items():
        assert count == 1, f"{route}: repeated paragraph: {paragraph}"
    for path in sorted(files):
        text = path.read_text()
        for link in LINKS.findall(text):
            destination = _destination(path, link)
            if destination is None:
                continue
            target, fragment = destination
            assert target.exists(), f"{route}: dead link: {link} in {path}"
            if fragment:
                headings = re.findall(r"^#+ (.+)$", target.read_text(), re.M)
                assert fragment in {
                    _slug(heading) for heading in headings
                }, f"{route}: missing heading: {link} in {path}"
        for code in CODES.findall(text):
            command = re.match(r"python ((?:scripts/|routes/)[^\s]+\.py)(?:\s|$)", code)
            if command:
                owner = {
                    'academic-writing.md': 'academic',
                    'fiction-writing.md': 'fiction',
                    'investigation.md': 'investigation',
                    'travel-guide.md': 'travel',
                }[route]
                relative = command[1].replace('<route>', owner)
                script = next(
                    (base / relative for base in (SKILL, ROOT) if (base / relative).is_file()), None
                )
                assert script is not None, f"{route}: missing script: {code}"
                if script not in help_options:
                    done = subprocess.run(
                        [sys.executable, str(script), "--help"],
                        cwd=SKILL,
                        text=True,
                        capture_output=True,
                    )
                    assert (
                        done.returncode == 0
                    ), f"{route}: cannot read script options: {code}: {done.stderr}"
                    help_options[script] = set(re.findall(r"--[a-z0-9][\w-]*", done.stdout))
                for flag in re.findall(r"--[a-z0-9][\w-]*", code):
                    assert flag in help_options[script], f"{route}: unknown option: {code}"
            if (
                code.startswith(("scripts/", "references/", "assets/", "routes/"))
                and "<" not in code
                and "*" not in code
            ):
                relative = code.split()[0].split("#", 1)[0]
                assert any(
                    (base / relative).exists() for base in (SKILL, ROOT)
                ), f"{route}: missing path: {code}"


def test_route_texts_have_no_repeats_dead_links_or_missing_names():
    errors = []
    help_options = {}
    route_root = SKILL / "references/routes"
    for route in sorted(route_root.glob("*.md")):
        files = set()
        todo = [SKILL / "SKILL.md", route]
        while todo:
            path = todo.pop().resolve()
            if path in files:
                continue
            files.add(path)
            if not path.is_file():
                continue
            for link in LINKS.findall(path.read_text()):
                destination = _destination(path, link)
                if destination is None:
                    continue
                target, fragment = destination
                if target.suffix != ".md" or not target.is_relative_to(SKILL):
                    continue
                if target.parent == route_root and target != route:
                    continue
                todo.append(target)
        try:
            for path in files:
                assert path.is_file(), f"{route.name}: missing reference: {path}"
            _check(route.name, files, help_options)
        except AssertionError as error:
            errors.append(str(error))
        print(
            f"route {route.name}: {sum(len(p.read_text()) for p in files if p.is_file())} characters, {len(files)} files"
        )
    assert not errors, "\n".join(errors)


def test_skill_entry_names_the_split_rule_once():
    text = (SKILL / "SKILL.md").read_text()
    assert text.count("split it into child units (parent_unit_id)") == 1
    assert [line for line in text.splitlines() if line.startswith("## ")][
        0
    ] == "## Start from the model"


def test_relocated_paragraphs_have_one_authority():
    counts=Counter(hashlib.sha256(part.strip().encode()).hexdigest()
        for path in SKILL.rglob('*.md') if 'references' in path.parts
        for part in path.read_text().split('\n\n') if len(part)>100)
    for digest in MOVED_PARAGRAPHS:
        assert counts[digest]==1,digest


MOVED_PARAGRAPHS=['04588da78a1a6985695e3d4eb5eedd5dc881bec7a14182bdf3476a8f3092f7f7', '070ad0db244235ae59ff7ec9574fb6f528513a18349ed04a9938fdaf478c85de', '0c036458a026216c574c24b43fe5e3ffda7eebbb90e1a7f2a3a6a85d21289ad7', '0d8195e6cbdfb8c5e50f8b8f0923a6a5297fdfcde01111509ee8476dd063c1a4', '0ea1e4f76ecb0be7f0b50e26a3a59a308f7bc397f168c604390f4e30e48ae623', '10fdb6d578f032b6482ac4eeabd3414f37ec404eeb81eb9de082e6adf878c93a', '12ab0a55b91dc0d9a85fe6bac8af7830bffdd49e61a81e4a1fbeeacd9883f5b6', '13b94faddefc857f52496e93c91de4b207848f8f6493ad6291cc9d1409c61907', '17cf7e806da8a9b988c6ab4264bcddf43c04a550d381bb6949a576c8f857fa25', '199fa64a2ad87b102e6e5503aae62fb7c193f9d0b31560f61c51b468dd72b3f9', '1aa176a8c01dc9bf005a4f3c33b3371fefee3651582faf5ba422f70b0422a815', '1af0332c0d58e86c9b90033d36b282e7ca624c7a7610accd86dc024366ab2f58', '1bc528fbb843fd2111029d84b259081909036278ffebe7e779f9277d76e86b06', '1c9ce48b48fc0226a389f134d7e62c83e6e9307248c1f39222d8bab9cdc891a6', '1d111f4daabbcc919102e86970a1c5e7398faebb9f8bf4e8dcc46801b26ea5d3', '2029296a1b32011dcd42aa04cc9c5c2efd123364b07759c37b0cdc1b4f9c540c', '22d8fb8ed8207fc0f34e3b4adbe5c457d993d7f376e0f3a4c6cef010857e29ed', '23ce72bd4283b8a8b1a57f1ff2497a082ab2a5cfc348737e815acebff9254554', '25068f7680d81e590e0cf84019bf8be692df29a5f5e4a7ace71dbe06bf8c8e61', '269acd1b4f20ec18eabeee082bffb0e35f7b376f3deb97a5abc80ba1d58ba802', '28ee488cadad6d8af65061a4d28e881c9f9ea168b055bf163769de68292db383', '297cbab509d24c3d86039ab942bc9fe4e57ec857bd5fdabb238d08660c048a44', '2a48123d779666ac365bca8e30bfe807c00cc6ac67ed16070e6420a26c626a6b', '2ab9fbf6fd2682d002911038a0ef6de3917d9067e6b4d15a19e771611eab186a', '2bc90f9f4a1b22c50a51f801659d2aea185d841d6f2f8f8d8a895c25e753c309', '2c3eb8b265f1728178295f447860c6c347468d2f76f26f40f34563c2699effae', '2dd6e00155672f192e9c6b25e21fb1b3d52000d6bf3fcd1bec61acd60e0377aa', '2f2b95b6bb5d4daef9f8f274980972290ab47db22f1c87cad9610ea07aef1142', '3046ce13b0ed0d23bc32083b3c59e7b1e64a8fdae6975b1bf6c1340ac09c4716', '328bb43a4ee27766e61b945e1d0f95faef9980dd7b506e312ae2b71c3aff583f', '347fbe52fe68b88708c4d49439ee1b2cb3f7b7cb64557db578d704f4878083f2', '382138671d0675874b4b80c31390d3a5fbd582bbc5f6d4a3d019220327522496', '3b92a2d89f57f39d287a5eec6481039df07567d34d56223b12de38ef55f63881', '3b95dd336d19c7a72fa8e4f8c785095a45352bfe077458e8ef6679c2b5b379fa', '3bb2abe5487791126092af23d4f49a566c5786b72e5f77ed418a4538755b35fc', '3e55000721f73057d87fb84b8cc118ad3781c9a50499b40dc2e2a72e80513bc4', '3e638fd1c5e33c6cc65d973392ce7ea49cdd4f570e05a4c301ac166a9a9bdc60', '3f0fab0cd0b8c8b44e78e8947ff001e9c0d25752573793b900afd447bb519b24', '412e254dab325fd4e8d942a0297b88877aa7c07d6b7e1d936f5ded33af48f602', '4188a0a25929e74e35668142a6ced67f5790ae4469b8a94495a2a7b8b3ef5caa', '42fff7926d96e57f1a8f0cc5837a4fee7c97bb15eb21b4e8b431b3d5da6d17ee', '498b6e3f9601264034911214d3a2a8632784986367464ad0e1c1df0e3188d588', '49a4dde70478273cff906330518d5103216e62c5e77ad53d41f12980cb016336', '4b315dbb3ed0e8e88a94490aabe931c70f6f4ff828a7539926cea8b523431032', '4c28790014973778b7f97c51d8741232aed8e2b5883c65f1342ac1035e56b66a', '4f1b613c11cadbe6a95c735ed4c278979826049fa4466ecf3735b26728743334', '4f55c7e1edac47c9ff5ffe00b66b6ea19414c62f5adc6cbff0cdd3261ea57844', '51983a749c538303772cddfbfaa93638fea82c13a9a71ce590993d3175ab3752', '51bdbe4216515c717bc5e23cd0ce496a1d87249892f5450d8163e46a15ed24a1', '520fc8c9e69864cb3e3ba93b952d35b8e82ae9f98d61de8ad38914938c678c88', '55b629e158c4136213029a857d6d26270c7f7605c7279db8e0f6334d977e3c36', '56537b13559f9277b5aebb66183810d01ffece1318461671126b7818ea265be9', '56d6dfd5164b1d6b3c15803e360246029aea1c3a8a23054daa903b77a084836e', '57e5419d1c2820964dc797a70a3f178736b6e01ead929f8efe9362565a0818cb', '5a71f002b379b87b9d7333aad8fe47cbfca84f02e75fab1f402f56af59e9ef34', '5b69d19fdfa8e896128d4b2d376e1575c3e5673d0626fcf063a221cc7f9ee4b7', '5bbc97145f929b51241fda506634785c7c6f2de58553123443aa57a055bdf06e', '5bcf0740904a2d15fe290db2cc5b855a4e6605808c41e57d6d40083dd8bee1a2', '5d71ba97cbef38d445f4f5cad9e5ff6059f8743d36c09c5a537e0689ed87a34f', '5ec01521bf2b17812f6260fa511b4238f507def0f6eadc2d7f5177eeb93a0370', '5f8840764d7ad3cb7b138f05bae289840e4600bef558e9e5b902eeada022824f', '61966bda08814e5a9d37ecc70c264ddc51139d7cf18555fd5c84cca9d354cecf', '69b76a601f3c1ed92d812df5f66fa32d689262fdd5970468b8876d7456086e27', '6daa82b5cc1909794ea72e7894b03ae8746dc2d3fd935867dea1464d39b77a55', '6eba302ba0b98ad12474651eeee2f0d0b8a3cb74301d0c545717afba3b41b4a6', '6fa374d552da7aac6cc8185a55a7260e457a4d9f73c7c7046faaa8bc86596824', '70d29e3f85ff67dcb7cacf56b7ce73e115339144af354e9345a2b549cbddc19e', '5316f7afe82c65ec4ca3daa7d00b3457a8236b83e3009a79925918a2f9683631', '7256ef01b93ef8bbc3dc030c64f8348a55a3cfbbe672d2085718ae2ab60db11e', '72ba1b414aee25c52bf749b6734941a3f669e36c8935f420df872403cf485742', '77832889ae78137a68fdf03973b2d5a73b12dd6b39d297126843ae264b11acd2', '793c68b0787689b1f1d71341a98b675a1587382a210de3164a46e4b96231b6dc', '7a95f9e133dc16244e49184b285c2ac255c749d1f9015fcf5cea40c289a0efca', '7c583c1f01c2aaaea3cdd0aa4838fea05269da6adb97b4b55f520a3660bd5321', '7e1fcac4f43806cb08a3a6c4a5bc156491a378572f49f386d5396e5ed8e32b7c', '7fd428ef9537e50af66cfcfc4b97ae4a073375abd2f4d5c0462293e33fed54f8', '801b9cb34b93b6043b85307a21789a9cffe2e18eb351894e6c0f3416cc7b9860', '80fd60e2f8224265a14fdc5c3153c5ec6d6e9c2d56fd7c26a5d3b425f9d9f244', '8132e60f004827a88bb81ec794b6d9fcc9e361cecd705fac94c77ea1870761ec', '81dc2e25b61bdee446f43346fc285d15661e3e736e755465815c9f814e821fb9', '823205eec8e75934f2fbf75d321948b530238f13ff0c77e9cee25db795edb55d', '8532162116a57bf5b320c23aa0e9692a9bac155439324ab1b0e6d9a49491ced6', '85b10b13e62a4228a0218348b5937478308db6492601ad30c3477e1a1cdba9b8', '865e48f3533f2105725dfce5fd64f2c447bacf2a21ab59197d0093c5f51c4823', '867ee0b3f2ac958f3bab6ccf1bb00c3483a7fbeac0322a4902ef76a392b89d9a', '8acda4960b8f24e242b2d8c9d402711044bddd1c53447ca478277f6cdb5a60ec', '8b0c062457e904eedb39661963029d35c5140d6acd71de94e7c9c701d4352fe1', '8f5113609281c53e30632dda00d6e8d8fa79d461b1f3dc0a1cd64c4866871c07', '8fc07df4b4ebcc42fd3c655b908348c1b16f81aacd23fa55d1916b9c27d3c02a', '92a86638809d06da17bb6228551cf3ebdab7d01c8e4dd9db58c87fd6b159b86a', '96f2bd37b59df314561dceb20be925bc56aed5208109f66bc730afd96f49e792', '97cb410c1f6110b4236c40b39ac795099071d0f86eedfa66db42178a8abf9ed6', '9b821d00fb0de6957f54f31b89ff046e81d5958c9031cd8cd8eabda69eae5ad4', '9b8f2f0e23850842d129469b7a4655bb1cccd674b50327c68e06531e3e05e9e2', '9d1725a804323c84f683e6037a3222cfa8e761cbd85dc56d2d744d1912387f70', '9db82b27e2335dd9ef858966dfd5c5cef422a19d2e053ce5cfb197fd674ff517', '9e37ff7eb93e21d7895f186e7a36b27a4a03fd39b61f429665b500dbdb7ee16e', 'a4933833016eb85c0ca374302791f2370d4a5acc5475703f28ce431c6f6aabad', 'a6006baa49b673021d65a1bd339664d59a3b301c044f6d895cb7131494f4b02d', 'a72f4b4555f547c5fc7213e413e0d08ff5613d72ab4b95b7c0899b998f25ed22', 'a96dfc3321a7ea2c29dd1f3bfbc794b02c87353704b24adc69150bafaa168609', 'acbbde1b2ee88d780e69ba969378b06602df12faa1747ded3cc328c9bde44557', 'ad629e5202978c8b8a8a04f16d2bc89de198935ee49a0fd898ee0c0925421458', 'ae8f0044f6c11f3d918c87c846052f8f6af99edf26d90005e15d3ba2a38d40ad', 'af277fade650b631b45b0bc7b0d8c4b79a17c467c19f9c00fafd2ae554b850f9', 'b0cf57e1723990bfb75a2e087d3c0be8511ec17797ba6224fe9d4c1522dccd1a', 'b461319cc741cd0782981eda0317fdc1d88a6a417fbd55af6d9f8465a4f05a2a', 'b6b118387e2ac119b4eb5ccb51cf4878acea0df5544ce3ce3a6c35afa017a0b0', 'b7686e3b66e904b55d902ea0118d54ad8f46e64a0b346e607e133b723c613dba', 'b9483b7519a0e5cdb376976437f17b06f21e80629d47c6d3dd398b8ce68ee9e2', 'ba2ec629364b3efcfd71dc827a9e335f918954eac3b1e575182797a69e909b74', 'bac11239ec286c1bc0ce326a624fddf41dc7b2efd00d9dbb890cb4f430609359', 'badd2664bd8e316f3c1b25e0a929a1a9e88686d6e7b5507ff8665d63a0ab913e', 'bb3b4746e0ed2cd5c72b7e5f58bb8fd0988e93db497e768b6a2cf6688e6caf72', 'c21efe8d97080e550e1753654d52d07634f2530c3ad6dea0c2ff7fd41178e801', 'c4d603a3ed8ff14dbbbcaa9846f94822237849797f37661387fb4f796a71a004', 'c51d18496e004120cf063132052e6804255c09c3de0d44afb97602c2c8b93d88', 'c810d4244ca82c13469f646974377f0ecbe7806df2dea216c1093586daecbe2c', 'c880b34a3a60a7bc8109e4dd3498c4da172be328456833379825e3c70b67f60c', 'c8e1082be2fb1607cb13ebc29a3f895d0993bb6aa24cb1e5281037e3f5bb0d5a', 'c96fce31e17df8a027151f33a32c787368d824eebfd5eca2c9dfa07d34464c04', 'ca544e0680cdf7ee973cb834ba67fbea8d2ff91d58f87151fa047615716fad7e', 'caa8dea43729a874647dec33050066596c013dd8060757b4be89a69eaa2ff1b5', 'cbb51ed97d870fad09630324dfffbc6ddd517148caae0ebc092e6eb106997f5e', 'cc69ad214901794fea5b1da040b3cc3843cacedb1cc2cdc6065c4d53f2325392', 'd13b408bf723acfc19ef7f06c6ef5fc5ef2bfef8786a8b7cdbbdfca4f168d162', 'd420ce2e44fd3079a179a955e77977d284ce70cc248249e96c38bb076aaf1564', 'd57ad5118aee32acdc6f72dcce615e5007237c0bf75b25de36ff6dfa7cc4a433', 'da4c04842160fff33753f5044343966d340f4b0f7d03d6c2d4da6ba29b732e38', 'db9c25e7d8bc49517b7dc1c84aa5954e09ccae6a2d0fae84cf9f88887ee4a955', 'df737c0e4ebb1531a1f49a6d447e3627ffd8efff35a127d493131cf04170536d', 'e72b1aba0845b4ddd4e6069c773f03eb78c9c6cb86c15bbdad59e7d8f6db929e', 'e8349de604ca636a3cd2506fbdb67bbd5da7179e28173235220279824c9a47bc', 'eaf9f6318fa19e63f347b9c7feff1a8307a2ce93e4bfb71b2419d42cfb87b30e', 'eafae05120d3123c3496565ed02975beae4cfe3a209e8fce6b710e9e559a4ffc', 'ece528729cd61f5e01ec0299ce8eebc3475e8b11f6feb1d62d7bc9f89fc07432', 'ee9bc89311af46de593311976a6745ce8265b3c6b70e7f8274b28567e2f782f8', 'f021d3cebea74c84282eed615cc894cb4a80b5c4e44ced3210cd5cef814e1206', 'f0a16475aacf1a8fa7ef55db0d1970fe554a8e2c72e5dece4bce79d009abfce0', 'f3b7f51f0e93b615d93b7ac3d2688bafc29727051c24cc55b44650d6152b9557', 'f481d5d164d23a3b2e0c1a37b57652ffa81b28b75787d134e71917cc7b62f49e', 'f5b04e38ea13cc77444453c85d003c2a1a90c20cbad3d46e0e717df1e8cbfbc4', 'f83dd325ac536f5aec465aa434632e11f5894fa56a062e1f51c137036cf3a4c0', 'fb720822d9c2eeb8cb92005f376eeb0e8b4b27195ebd5af47d9e537905bef63d']
