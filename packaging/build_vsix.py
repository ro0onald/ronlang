"""Build the small, dependency-free VS Code extension as a VSIX archive."""
from pathlib import Path
import json
import zipfile
import sys

root = Path(__file__).resolve().parent.parent
editor = root / 'editor'
output = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'dist'
output.mkdir(parents=True, exist_ok=True)
package = json.loads((editor / 'package.json').read_text())
manifest = f'''<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata><Identity Language="en-US" Id="ronlang" Version="{package['version']}" Publisher="ronlang-local"/>
    <DisplayName>RonLang</DisplayName><Description xml:space="preserve">RonLang language support</Description>
    <Tags>ronlang,language</Tags><Categories>Programming Languages</Categories><GalleryFlags>Public</GalleryFlags>
    <Properties><Property Id="Microsoft.VisualStudio.Code.Engine" Value="^1.85.0"/>
    <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace"/>
    <Property Id="Microsoft.VisualStudio.Code.ExecutesCode" Value="true"/></Properties>
  </Metadata>
  <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation><Dependencies/>
  <Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/>
  <Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md" Addressable="true"/></Assets>
</PackageManifest>'''
content_types = '''<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="json" ContentType="application/json"/><Default Extension="js" ContentType="application/javascript"/>
<Default Extension="md" ContentType="text/markdown"/><Default Extension="vsixmanifest" ContentType="text/xml"/>
</Types>'''
target = output / 'ronlang-1.0.0-rc.1.vsix'
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('extension.vsixmanifest', manifest)
    archive.writestr('[Content_Types].xml', content_types)
    for file in editor.rglob('*'):
        if file.is_file():
            archive.write(file, 'extension/' + file.relative_to(editor).as_posix())
print(target)
