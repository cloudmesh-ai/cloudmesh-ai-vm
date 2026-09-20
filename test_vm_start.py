from cloudmesh.ai.command.vm import cmx
from click.testing import CliRunner

runner = CliRunner()
result = runner.invoke(cmx, ['vm', 'start'])
print(result.output)
