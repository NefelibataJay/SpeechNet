import torch
import torchaudio
from omegaconf import DictConfig
from torch.utils.data import Dataset
import librosa
import os

from tool.data_augmentations.speech_augment import SpecAugment
from util.tokenizer import Tokenizer


class SpeechToTextDataset(Dataset):
    def __init__(
            self,
            configs: DictConfig,
            tokenizer: Tokenizer,
            audio_paths: list,
            transcripts: list,
            sos_id: int = 1,
            eos_id: int = 2,
            spec_aug=True,
            # noise_augment=True,
    ):
        super(SpeechToTextDataset, self).__init__()
        self.tokenizer = tokenizer
        self.configs = configs
        self.sos_id = sos_id
        self.eos_id = eos_id

        self.num_mel_bins = configs.num_mel_bins
        self.sample_rate = configs.sample_rate

        self.feature_types = configs.feature_types

        assert self.feature_types in ["mfcc", "fbank", "spectrogram"], "feature_types not found"
        # TODO: using kaldi to generate feature
        if self.feature_types == "mfcc":
            self.extract_feature = torchaudio.transforms.MFCC(sample_rate=16000, n_mfcc=self.num_mel_bins)
        elif self.feature_types == "fbank":
            self.extract_feature = torchaudio.transforms.MelSpectrogram(sample_rate=16000, n_mels=self.num_mel_bins)
        elif self.feature_types == "spectrogram":
            self.extract_feature = torchaudio.transforms.Spectrogram(n_fft=400)

        self.audio_paths = audio_paths
        self.transcripts = transcripts
        if spec_aug:
            self.spec_aug = SpecAugment(**configs.spec_aug_conf)
        # TODO add sort
        # TODO add noise_augment

    def __len__(self):
        return len(self.audio_paths)

    def __getitem__(self, idx):
        speech_feature = self._parse_audio(self.audio_paths[idx])
        transcript = self._parse_transcript(self.transcripts[idx])
        input_lengths = speech_feature.size(0)  # time
        target_lengths = len(transcript)

        return speech_feature, input_lengths, transcript, target_lengths

    def _parse_transcript(self, tokens: str):
        transcript = list()
        # add sos and eos
        # transcript.append(self.sos_id)
        transcript.extend(self.tokenizer.text2int(tokens))
        # transcript.append(self.eos_id)

        return transcript

    def _parse_audio(self, audio_path):
        signal, sr = torchaudio.load(audio_path)

        if sr != self.sample_rate:
            signal = torchaudio.functional.resample(signal, sr, self.sample_rate)

        signal = signal * (1 << 15)

        feature = self.extract_feature(signal)
        feature = self.spec_aug(feature)

        # feature [1, dim, time] -> [time, dim]
        feature = feature.squeeze(0).transpose(1, 0)

        # spec_sub(feature)
        # spec_trim(feature)

        return feature
