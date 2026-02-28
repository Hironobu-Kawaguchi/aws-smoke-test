#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib/core';
import { NotepadStack } from '../lib/notepad-stack';

const app = new cdk.App();
new NotepadStack(app, 'NotepadStack', {
  env: {
    account: '235494796255',
    region: 'ap-northeast-1',
  },
});
