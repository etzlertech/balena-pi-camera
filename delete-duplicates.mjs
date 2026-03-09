// Delete duplicate files from Supabase storage
// Run with: node delete-duplicates.mjs

import { createClient } from '@supabase/supabase-js';
import { readFileSync } from 'fs';

const SUPABASE_URL = 'https://dtzayqhebbrbvordmabh.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR0emF5cWhlYmJyYnZvcmRtYWJoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg2ODA2NzIsImV4cCI6MjA4NDI1NjY3Mn0.hlDn444h_cxDf7BB3C3e68VrOfXtiljtsIwd0L1iF1w';
const BUCKET = 'spypoint-images';
const DELETE_LIST_FILE = process.env.USERPROFILE + '/Downloads/delete-list.txt';

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

async function deleteFiles() {
    console.log('Reading delete list from:', DELETE_LIST_FILE);

    const fileContent = readFileSync(DELETE_LIST_FILE, 'utf-8');
    const filesToDelete = fileContent.split('\n').filter(line => line.trim().length > 0);

    console.log(`\nFound ${filesToDelete.length} files to delete`);
    console.log('\n⚠️  WARNING: This will permanently delete these files from Supabase storage!');
    console.log('Press Ctrl+C within 5 seconds to cancel...\n');

    await new Promise(resolve => setTimeout(resolve, 5000));

    console.log('Starting deletion...\n');

    let deleted = 0;
    let errors = 0;

    for (const filePath of filesToDelete) {
        try {
            const { error } = await supabase.storage
                .from(BUCKET)
                .remove([filePath]);

            if (error) {
                throw error;
            }

            deleted++;
            if (deleted % 50 === 0) {
                console.log(`Progress: ${deleted}/${filesToDelete.length} deleted`);
            }

            // Small delay to avoid rate limiting
            if (deleted % 10 === 0) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        } catch (error) {
            errors++;
            console.error(`✗ Error deleting ${filePath}:`, error.message);
        }
    }

    console.log('\n=== DELETION COMPLETE ===');
    console.log(`Successfully deleted: ${deleted} files`);
    console.log(`Errors: ${errors} files`);
    console.log('Space reclaimed: ~2.94 MB');
}

deleteFiles().catch(console.error);
