import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, DeleteView, View, UpdateView
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from .models import Conversation, Message
from .forms import MessageForm
from .services.ai_service import AIService
from .services.exceptions import AIAssistantError
from .utils import sanitize_message, truncate_title


class ChatListView(LoginRequiredMixin, ListView):
    model = Conversation
    template_name = 'assistant/chat_list.html'
    context_object_name = 'conversations'

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = MessageForm()
        return context


class ChatDetailView(LoginRequiredMixin, DetailView):
    model = Conversation
    template_name = 'assistant/chat_list.html'
    context_object_name = 'active_conversation'

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['conversations'] = Conversation.objects.filter(user=self.request.user)
        context['form'] = MessageForm()
        context['messages'] = self.object.messages.all()
        return context


class ChatCreateView(LoginRequiredMixin, View):

    def get(self, request):
        conversation = Conversation.objects.create(user=request.user)
        return redirect('assistant:chat', pk=conversation.pk)

    def post(self, request):
        conversation = Conversation.objects.create(user=request.user)
        return redirect('assistant:chat', pk=conversation.pk)


class ChatDeleteView(LoginRequiredMixin, DeleteView):
    model = Conversation
    success_url = reverse_lazy('assistant:list')

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        return JsonResponse({'deleted': True})


class ChatRenameView(LoginRequiredMixin, UpdateView):
    model = Conversation
    fields = ['title']
    http_method_names = ['post']

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'title': self.object.title})

    def form_invalid(self, form):
        return JsonResponse({'error': 'Invalid title'}, status=400)


class ChatExportView(LoginRequiredMixin, DetailView):
    model = Conversation

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def render_to_response(self, context):
        conversation = self.object
        lines = [f'# {conversation.title}', '', f'*Exported from RittikDesk AI*', '', '---', '']
        for msg in conversation.messages.all():
            prefix = '**You:**' if msg.role == 'user' else '**Assistant:**'
            lines.append(f'{prefix}\n{msg.content}\n')
        content = '\n'.join(lines)
        filename = conversation.title.replace(' ', '_')[:50]
        response = HttpResponse(content, content_type='text/markdown')
        response['Content-Disposition'] = f'attachment; filename="{filename}.md"'
        return response


class ChatMessageView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
        form = MessageForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'error': 'Invalid message.'}, status=400)

        content = sanitize_message(form.cleaned_data['message'])
        Message.objects.create(conversation=conversation, role='user', content=content)

        if conversation.title == 'New Chat':
            conversation.title = truncate_title(content)
            conversation.save(update_fields=['title'])

        try:
            service = AIService()
            history = list(conversation.messages.all())
            reply = service.generate_response(history)
            Message.objects.create(conversation=conversation, role='assistant', content=reply)
            return JsonResponse({'reply': reply, 'conversation_id': conversation.pk})
        except AIAssistantError as e:
            return JsonResponse({'error': str(e)}, status=503)
