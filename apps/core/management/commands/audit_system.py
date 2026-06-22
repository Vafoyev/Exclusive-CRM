from django.core.management.base import BaseCommand
from django.urls import get_resolver, URLPattern, URLResolver
from django.template.loader import get_template
from django.template import TemplateDoesNotExist, TemplateSyntaxError
import os

class Command(BaseCommand):
    help = 'Scans project for URL and Template errors'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting Deep System Audit...'))
        
        # 1. CHECK TEMPLATES
        self.stdout.write('\n1. Checking Templates Syntax...')
        template_errors = 0
        from django.conf import settings
        
        template_dirs = settings.TEMPLATES[0]['DIRS']
        for template_dir in template_dirs:
            for root, dirs, files in os.walk(template_dir):
                for file in files:
                    if file.endswith('.html'):
                        path = os.path.join(root, file)
                        rel_path = os.path.relpath(path, template_dir).replace('\\', '/')
                        try:
                            get_template(rel_path)
                        except TemplateSyntaxError as e:
                            self.stdout.write(self.style.ERROR(f'[SYNTAX ERROR] {rel_path}: {e}'))
                            template_errors += 1
                        except TemplateDoesNotExist:
                            # Should not happen if we walk the dir, but possible with usage
                            pass
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'[ERROR] {rel_path}: {e}'))
                            template_errors += 1
        
        if template_errors == 0:
            self.stdout.write(self.style.SUCCESS('All templates compiled successfully.'))
        else:
            self.stdout.write(self.style.ERROR(f'Found {template_errors} template errors.'))

        # 2. CHECK URL REVERSAL (Static Check mostly)
        self.stdout.write('\n2. Listing All Valid URLs...')
        # Just listing them to ensure they load
        resolver = get_resolver()
        try:
            url_count = self.count_patterns(resolver.url_patterns)
            self.stdout.write(self.style.SUCCESS(f'Successfully loaded {url_count} URL patterns.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'URL Configuration Error: {e}'))

    def count_patterns(self, patterns):
        count = 0
        for pattern in patterns:
            if isinstance(pattern, URLPattern):
                count += 1
            elif isinstance(pattern, URLResolver):
                count += self.count_patterns(pattern.url_patterns)
        return count
