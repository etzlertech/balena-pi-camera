// Inspect actual filenames in Supabase storage
import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://dtzayqhebbrbvordmabh.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR0emF5cWhlYmJyYnZvcmRtYWJoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg2ODA2NzIsImV4cCI6MjA4NDI1NjY3Mn0.hlDn444h_cxDf7BB3C3e68VrOfXtiljtsIwd0L1iF1w';
const BUCKET = 'spypoint-images';

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

async function inspectFiles() {
    // Get a sample from QN folder
    const { data: files, error } = await supabase.storage
        .from(BUCKET)
        .list('QN', {
            limit: 20,
            sortBy: { column: 'created_at', order: 'desc' }
        });

    if (error) {
        console.error('Error:', error);
        return;
    }

    console.log('Sample files from QN folder:\n');
    files.forEach(file => {
        if (file.id !== null) { // Only files, not folders
            const sizeKB = (file.metadata?.size || 0) / 1024;
            console.log(`${file.name} - ${sizeKB.toFixed(2)} KB`);
        }
    });

    // Show files under 10KB
    console.log('\n\nFiles under 10 KB:');
    const smallFiles = files.filter(f => f.id !== null && (f.metadata?.size || 0) < 10240);
    smallFiles.forEach(file => {
        const sizeKB = (file.metadata?.size || 0) / 1024;
        console.log(`${file.name} - ${sizeKB.toFixed(2)} KB`);
    });

    console.log(`\nTotal small files (< 10KB): ${smallFiles.length} out of ${files.filter(f => f.id !== null).length} files`);
}

inspectFiles().catch(console.error);
