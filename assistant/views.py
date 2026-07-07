import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, DeleteView, View, UpdateView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect

from .models import Conversation, Message, Category
from .forms import MessageForm
from .services.ai_service import AIService
from .services.exceptions import AIAssistantError
from .utils import sanitize_message, truncate_title

logger = logging.getLogger(__name__)


def _common_context(user):
    conversations = Conversation.objects.filter(user=user)
    pinned = conversations.filter(pinned=True)
    categories = list(Category.objects.filter(user=user))
    category_data = [(c, conversations.filter(category=c, pinned=False)) for c in categories]
    general = conversations.filter(category__isnull=True, pinned=False)
    return {
        'categories': categories,
        'category_data': category_data,
        'pinned_conversations': pinned,
        'uncategorized_conversations': general,
    }


class ChatListView(LoginRequiredMixin, ListView):
    model = Conversation
    template_name = 'assistant/chat_list.html'
    context_object_name = 'conversations'

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = MessageForm()
        context.update(_common_context(self.request.user))
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
        context.update(_common_context(self.request.user))
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


class ChatMessageStreamView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)

        is_regenerate = request.POST.get('regenerate') == 'true'

        if not is_regenerate:
            form = MessageForm(request.POST)
            if not form.is_valid():
                return JsonResponse({'error': 'Invalid message.'}, status=400)
            content = sanitize_message(form.cleaned_data['message'])
            Message.objects.create(conversation=conversation, role='user', content=content)

            if conversation.title == 'New Chat':
                conversation.title = truncate_title(content)
                conversation.save(update_fields=['title'])

        def event_stream():
            full_content = ''
            saved = False
            try:
                history = list(conversation.messages.all())
                service = AIService()
                for token in service.generate_stream(history):
                    full_content += token
                    yield f'data: {json.dumps({"t": token})}\n\n'

                Message.objects.create(
                    conversation=conversation, role='assistant', content=full_content
                )
                saved = True
                yield f'data: {json.dumps({"done": True})}\n\n'
            except AIAssistantError as e:
                logger.error('Stream AI error: %s', e)
                yield f'data: {json.dumps({"e": str(e)})}\n\n'
            except Exception as e:
                logger.exception('Stream unexpected error')
                yield f'data: {json.dumps({"e": "An unexpected error occurred."})}\n\n'
            finally:
                if full_content and not saved:
                    try:
                        Message.objects.create(
                            conversation=conversation, role='assistant', content=full_content
                        )
                    except Exception:
                        logger.exception('Failed to save partial streamed message')

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ChatEditMessageView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        message = get_object_or_404(Message, pk=pk, conversation__user=request.user, role='user')
        content = sanitize_message(request.POST.get('message', ''))
        if not content:
            return JsonResponse({'error': 'Message cannot be empty.'}, status=400)

        message.content = content
        message.save(update_fields=['content'])
        conversation = message.conversation
        conversation.messages.filter(pk__gt=pk).delete()

        if conversation.title == 'New Chat':
            conversation.title = truncate_title(content)
            conversation.save(update_fields=['title'])

        def event_stream():
            full_content = ''
            saved = False
            try:
                history = list(conversation.messages.all())
                service = AIService()
                for token in service.generate_stream(history):
                    full_content += token
                    yield f'data: {json.dumps({"t": token})}\n\n'

                Message.objects.create(
                    conversation=conversation, role='assistant', content=full_content
                )
                saved = True
                yield f'data: {json.dumps({"done": True})}\n\n'
            except AIAssistantError as e:
                logger.error('Edit stream AI error: %s', e)
                yield f'data: {json.dumps({"e": str(e)})}\n\n'
            except Exception as e:
                logger.exception('Edit stream unexpected error')
                yield f'data: {json.dumps({"e": "An unexpected error occurred."})}\n\n'
            finally:
                if full_content and not saved:
                    try:
                        Message.objects.create(
                            conversation=conversation, role='assistant', content=full_content
                        )
                    except Exception:
                        logger.exception('Failed to save edited streamed message')

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ChatPinToggleView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
        conversation.pinned = not conversation.pinned
        conversation.save(update_fields=['pinned'])
        return JsonResponse({'pinned': conversation.pinned})


class CategoryCreateView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request):
        name = request.POST.get('name', '').strip()
        if not name:
            return JsonResponse({'error': 'Name is required'}, status=400)
        max_order = Category.objects.filter(user=request.user).aggregate(m=Max('order'))['m'] or 0
        cat = Category.objects.create(user=request.user, name=name, order=max_order + 1)
        return JsonResponse({'id': cat.pk, 'name': cat.name, 'order': cat.order})


class CategoryRenameView(LoginRequiredMixin, UpdateView):
    model = Category
    fields = ['name']
    http_method_names = ['post']

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

    def form_valid(self, form):
        self.object = form.save()
        return JsonResponse({'id': self.object.pk, 'name': self.object.name})

    def form_invalid(self, form):
        return JsonResponse({'error': 'Invalid name'}, status=400)


class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    http_method_names = ['post']

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.conversations.update(category=None)
        self.object.delete()
        return JsonResponse({'deleted': True})


class ConversationMoveCategoryView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
        category_id = request.POST.get('category_id')
        if category_id:
            category = get_object_or_404(Category, pk=category_id, user=request.user)
            conversation.category = category
        else:
            conversation.category = None
        conversation.save(update_fields=['category'])
        return JsonResponse({'success': True})
