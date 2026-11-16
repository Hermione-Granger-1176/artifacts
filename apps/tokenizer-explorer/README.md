# Tokenizer: temperature and top-p explorer

This interactive explainer shows how temperature and top-p change next-token sampling. It also includes illustrative byte-pair encoding (BPE) token splits and concept cards.

## Features

- A prompt shown as colored token chips, with the completion blank at the end of the line.
- A next-token list with each candidate's shaped odds, its renormalized draw chance, and, after 100 samples, its observed count.
- Tokens cut by top-p stay in the list, struck through, below a "top P cut" line.
- A scenario dropdown, a temperature slider (0 to 3.0, where 0 is greedy decoding, default 1.0), a top-p slider (0.01 to 1.0, default 0.70), and Precise, Chat, and Creative presets.
- Tokenization examples with token and character counts.
- Expandable concept cards, and the sampling pseudocode under "Show the code".

## Use the app

- Pick a scenario from the dropdown. Each scenario has its own candidate tokens and probabilities.
- Move the temperature or top-p slider, or click a preset. The note under each slider explains the current setting.
- Click **Pick next token** to draw one token. Click **Sample 100x** to draw 100 tokens and fill the Seen column. Click **Reset** to clear the picks and tallies.
- Click **Show whitespace** to show leading spaces as dots in the prompt and in the tokenization examples.
- Open a concept card to read more about it.

## Made with

- Claude

## Documentation

The app documentation covers [architecture](docs/architecture.md), [verification](docs/verification.md), and [implementation decisions](docs/decisions.md).
