import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import path from 'path';
import { promisify } from 'util';

const execAsync = promisify(exec);

export async function GET() {
  try {
    const projectRoot = path.resolve(process.cwd(), '..');
    const cmd = `PYTHONPATH=. .venv/bin/python scripts/console_api.py get_data`;
    const { stdout, stderr } = await execAsync(cmd, { cwd: projectRoot });
    if (stderr && !stdout) {
      return NextResponse.json({ error: stderr }, { status: 500 });
    }
    const data = JSON.parse(stdout);
    return NextResponse.json(data);
  } catch (error: any) {
    console.error('Error fetching data:', error);
    return NextResponse.json({ error: error.message || 'Internal Server Error' }, { status: 500 });
  }
}
