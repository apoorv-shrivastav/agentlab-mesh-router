import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import path from 'path';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function POST(req: Request) {
  try {
    const { action, clusterId } = await req.json();
    const projectRoot = path.resolve(process.cwd(), '..');
    
    let cmd = '';
    if (action === 'approve') {
      if (!clusterId) {
        return NextResponse.json({ error: 'Missing clusterId' }, { status: 400 });
      }
      cmd = `PYTHONPATH=. .venv/bin/python scripts/console_api.py approve ${clusterId}`;
    } else if (action === 'reject') {
      if (!clusterId) {
        return NextResponse.json({ error: 'Missing clusterId' }, { status: 400 });
      }
      cmd = `PYTHONPATH=. .venv/bin/python scripts/console_api.py reject ${clusterId}`;
    } else if (action === 'trigger_failure') {
      cmd = `PYTHONPATH=. .venv/bin/python scripts/console_api.py trigger_failure`;
    } else {
      return NextResponse.json({ error: `Unknown action: ${action}` }, { status: 400 });
    }

    const { stdout, stderr } = await execAsync(cmd, { cwd: projectRoot });
    if (stderr && !stdout) {
      return NextResponse.json({ error: stderr }, { status: 500 });
    }
    const data = JSON.parse(stdout);
    return NextResponse.json(data);
  } catch (error: any) {
    console.error('Error executing action:', error);
    return NextResponse.json({ error: error.message || 'Internal Server Error' }, { status: 500 });
  }
}
